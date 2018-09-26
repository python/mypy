"""Low-level infrastructure to find modules."""

import os

from typing import Dict, List, NamedTuple, Optional, Set, Tuple

MYPY = False
if MYPY:
    from typing_extensions import Final

from mypy.fscache import FileSystemCache
from mypy.options import Options

# python_path is user code, mypy_path is set via config or environment variable,
# package_path is calculated by _get_site_packages_dirs, and typeshed_path points
# to typeshed. Each is a tuple of paths to be searched in find_module()
SearchPaths = NamedTuple('SearchPaths',
             (('python_path', Tuple[str, ...]),
              ('mypy_path', Tuple[str, ...]),
              ('package_path', Tuple[str, ...]),
              ('typeshed_path', Tuple[str, ...])))

# Package dirs are a two-tuple of path to search and whether to verify the module
OnePackageDir = Tuple[str, bool]
PackageDirs = List[OnePackageDir]

PYTHON_EXTENSIONS = ['.pyi', '.py']  # type: Final


class BuildSource:
    def __init__(self, path: Optional[str], module: Optional[str],
                 text: Optional[str], base_dir: Optional[str] = None) -> None:
        self.path = path
        self.module = module or '__main__'
        self.text = text
        self.base_dir = base_dir

    def __repr__(self) -> str:
        return '<BuildSource path=%r module=%r has_text=%s>' % (self.path,
                                                                self.module,
                                                                self.text is not None)


class FindModuleCache:
    """Module finder with integrated cache.

    Module locations and some intermediate results are cached internally
    and can be cleared with the clear() method.

    All file system accesses are performed through a FileSystemCache,
    which is not ever cleared by this class. If necessary it must be
    cleared by client code.
    """

    def __init__(self, fscache: Optional[FileSystemCache] = None,
                 options: Optional[Options] = None) -> None:
        self.fscache = fscache or FileSystemCache()
        # Cache find_lib_path_dirs: (dir_chain, search_paths) -> list(package_dirs, should_verify)
        self.dirs = {}  # type: Dict[Tuple[str, Tuple[str, ...]], PackageDirs]
        # Cache find_module: (id, search_paths, python_version) -> result.
        self.results = {}  # type: Dict[Tuple[str, SearchPaths, Optional[str]], Optional[str]]
        self.options = options

    def clear(self) -> None:
        self.results.clear()
        self.dirs.clear()

    def find_lib_path_dirs(self, dir_chain: str, lib_path: Tuple[str, ...]) -> PackageDirs:
        # Cache some repeated work within distinct find_module calls: finding which
        # elements of lib_path have even the subdirectory they'd need for the module
        # to exist. This is shared among different module ids when they differ only
        # in the last component.
        # This is run for the python_path, mypy_path, and typeshed_path search paths
        key = (dir_chain, lib_path)
        if key not in self.dirs:
            self.dirs[key] = self._find_lib_path_dirs(dir_chain, lib_path)
        return self.dirs[key]

    def _find_lib_path_dirs(self, dir_chain: str, lib_path: Tuple[str, ...]) -> PackageDirs:
        dirs = []
        for pathitem in lib_path:
            # e.g., '/usr/lib/python3.4/foo/bar'
            dir = os.path.normpath(os.path.join(pathitem, dir_chain))
            if self.fscache.isdir(dir):
                dirs.append((dir, True))
        return dirs

    def find_module(self, id: str, search_paths: SearchPaths,
                    python_executable: Optional[str]) -> Optional[str]:
        """Return the path of the module source file, or None if not found."""
        key = (id, search_paths, python_executable)
        if key not in self.results:
            self.results[key] = self._find_module(id, search_paths, python_executable)
        return self.results[key]

    def _find_module_non_stub_helper(self, components: List[str],
                                     pkg_dir: str) -> Optional[OnePackageDir]:
        dir_path = pkg_dir
        for index, component in enumerate(components):
            dir_path = os.path.join(dir_path, component)
            if self.fscache.isfile(os.path.join(dir_path, 'py.typed')):
                return os.path.join(pkg_dir, *components[:-1]), index == 0
        return None

    def _find_module(self, id: str, search_paths: SearchPaths,
                     python_executable: Optional[str]) -> Optional[str]:
        fscache = self.fscache

        # If we're looking for a module like 'foo.bar.baz', it's likely that most of the
        # many elements of lib_path don't even have a subdirectory 'foo/bar'.  Discover
        # that only once and cache it for when we look for modules like 'foo.bar.blah'
        # that will require the same subdirectory.
        components = id.split('.')
        dir_chain = os.sep.join(components[:-1])  # e.g., 'foo/bar'
        # TODO (ethanhs): refactor each path search to its own method with lru_cache

        # We have two sets of folders so that we collect *all* stubs folders and
        # put them in the front of the search path
        third_party_inline_dirs = []  # type: PackageDirs
        third_party_stubs_dirs = []  # type: PackageDirs
        # Third-party stub/typed packages
        for pkg_dir in search_paths.package_path:
            stub_name = components[0] + '-stubs'
            stub_dir = os.path.join(pkg_dir, stub_name)
            if fscache.isdir(stub_dir):
                stub_typed_file = os.path.join(stub_dir, 'py.typed')
                stub_components = [stub_name] + components[1:]
                path = os.path.join(pkg_dir, *stub_components[:-1])
                if fscache.isdir(path):
                    if fscache.isfile(stub_typed_file):
                        # Stub packages can have a py.typed file, which must include
                        # 'partial\n' to make the package partial
                        # Partial here means that mypy should look at the runtime
                        # package if installed.
                        if fscache.read(stub_typed_file).decode().strip() == 'partial':
                            runtime_path = os.path.join(pkg_dir, dir_chain)
                        third_party_inline_dirs.append((runtime_path, True))
                        # if the package is partial, we don't verify the module, as
                        # the partial stub package may not have a __init__.pyi
                        third_party_stubs_dirs.append((path, False))
                    else:
                        third_party_stubs_dirs.append((path, True))
            non_stub_match = self._find_module_non_stub_helper(components, pkg_dir)
            if non_stub_match:
                third_party_inline_dirs.append(non_stub_match)
        if self.options and self.options.use_builtins_fixtures:
            # Everything should be in fixtures.
            third_party_inline_dirs.clear()
            third_party_stubs_dirs.clear()
        python_mypy_path = search_paths.python_path + search_paths.mypy_path
        candidate_base_dirs = self.find_lib_path_dirs(dir_chain, python_mypy_path) + \
            third_party_stubs_dirs + third_party_inline_dirs + \
            self.find_lib_path_dirs(dir_chain, search_paths.typeshed_path)

        # If we're looking for a module like 'foo.bar.baz', then candidate_base_dirs now
        # contains just the subdirectories 'foo/bar' that actually exist under the
        # elements of lib_path.  This is probably much shorter than lib_path itself.
        # Now just look for 'baz.pyi', 'baz/__init__.py', etc., inside those directories.
        seplast = os.sep + components[-1]  # so e.g. '/baz'
        sepinit = os.sep + '__init__'
        for base_dir, verify in candidate_base_dirs:
            base_path = base_dir + seplast  # so e.g. '/usr/lib/python3.4/foo/bar/baz'
            # Prefer package over module, i.e. baz/__init__.py* over baz.py*.
            for extension in PYTHON_EXTENSIONS:
                path = base_path + sepinit + extension
                path_stubs = base_path + '-stubs' + sepinit + extension
                if fscache.isfile_case(path):
                    if verify and not verify_module(fscache, id, path):
                        continue
                    return path
                elif fscache.isfile_case(path_stubs):
                    if verify and not verify_module(fscache, id, path_stubs):
                        continue
                    return path_stubs
            # No package, look for module.
            for extension in PYTHON_EXTENSIONS:
                path = base_path + extension
                if fscache.isfile_case(path):
                    if verify and not verify_module(fscache, id, path):
                        continue
                    return path
        return None

    def find_modules_recursive(self, module: str, search_paths: SearchPaths,
                               python_executable: Optional[str]) -> List[BuildSource]:
        module_path = self.find_module(module, search_paths, python_executable)
        if not module_path:
            return []
        result = [BuildSource(module_path, module, None)]
        if module_path.endswith(('__init__.py', '__init__.pyi')):
            # Subtle: this code prefers the .pyi over the .py if both
            # exists, and also prefers packages over modules if both x/
            # and x.py* exist.  How?  We sort the directory items, so x
            # comes before x.py and x.pyi.  But the preference for .pyi
            # over .py is encoded in find_module(); even though we see
            # x.py before x.pyi, find_module() will find x.pyi first.  We
            # use hits to avoid adding it a second time when we see x.pyi.
            # This also avoids both x.py and x.pyi when x/ was seen first.
            hits = set()  # type: Set[str]
            for item in sorted(self.fscache.listdir(os.path.dirname(module_path))):
                abs_path = os.path.join(os.path.dirname(module_path), item)
                if os.path.isdir(abs_path) and \
                        (os.path.isfile(os.path.join(abs_path, '__init__.py')) or
                        os.path.isfile(os.path.join(abs_path, '__init__.pyi'))):
                    hits.add(item)
                    result += self.find_modules_recursive(module + '.' + item, search_paths,
                                                          python_executable)
                elif item != '__init__.py' and item != '__init__.pyi' and \
                        item.endswith(('.py', '.pyi')):
                    mod = item.split('.')[0]
                    if mod not in hits:
                        hits.add(mod)
                        result += self.find_modules_recursive(module + '.' + mod, search_paths,
                                                              python_executable)
        return result


def verify_module(fscache: FileSystemCache, id: str, path: str) -> bool:
    """Check that all packages containing id have a __init__ file."""
    if path.endswith(('__init__.py', '__init__.pyi')):
        path = os.path.dirname(path)
    for i in range(id.count('.')):
        path = os.path.dirname(path)
        if not any(fscache.isfile_case(os.path.join(path, '__init__{}'.format(extension)))
                   for extension in PYTHON_EXTENSIONS):
            return False
    return True
