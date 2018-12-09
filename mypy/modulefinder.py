"""Low-level infrastructure to find modules.

This build on fscache.py; find_sources.py builds on top of this.
"""

import ast
import collections
import functools
import os
import subprocess
import sys

from typing import Dict, List, NamedTuple, Optional, Set, Tuple

MYPY = False
if MYPY:
    from typing_extensions import Final

from mypy.defaults import PYTHON3_VERSION_MIN
from mypy.fscache import FileSystemCache
from mypy.options import Options
from mypy import sitepkgs

# Paths to be searched in find_module().
SearchPaths = NamedTuple(
    'SearchPaths',
    [('python_path', Tuple[str, ...]),  # where user code is found
     ('mypy_path', Tuple[str, ...]),  # from $MYPYPATH or config variable
     ('package_path', Tuple[str, ...]),  # from get_site_packages_dirs()
     ('typeshed_path', Tuple[str, ...]),  # paths in typeshed
     ])

# Package dirs are a two-tuple of path to search and whether to verify the module
OnePackageDir = Tuple[str, bool]
PackageDirs = List[OnePackageDir]

PYTHON_EXTENSIONS = ['.pyi', '.py']  # type: Final


class BuildSource:
    """A single source file."""

    def __init__(self, path: Optional[str], module: Optional[str],
                 text: Optional[str], base_dir: Optional[str] = None) -> None:
        self.path = path  # File where it's found (e.g. 'xxx/yyy/foo/bar.py')
        self.module = module or '__main__'  # Module name (e.g. 'foo.bar')
        self.text = text  # Source code, if initially supplied, else None
        self.base_dir = base_dir  # Directory where the package is rooted (e.g. 'xxx/yyy')

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

    def __init__(self,
                 search_paths: SearchPaths,
                 fscache: Optional[FileSystemCache] = None,
                 options: Optional[Options] = None) -> None:
        self.search_paths = search_paths
        self.fscache = fscache or FileSystemCache()
        # Cache find_lib_path_dirs: (dir_chain, search_paths) -> list(package_dirs, should_verify)
        self.dirs = {}  # type: Dict[Tuple[str, Tuple[str, ...]], PackageDirs]
        # Cache find_module: id -> result
        self.results = {}  # type: Dict[str, Optional[str]]
        self.ns_ancestors = {}  # type: Dict[str, str]
        self.options = options

    def clear(self) -> None:
        self.results.clear()
        self.dirs.clear()
        self.ns_ancestors.clear()

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

    def find_module(self, id: str) -> Optional[str]:
        """Return the path of the module source file, or None if not found."""
        if id not in self.results:
            self.results[id] = self._find_module(id)
        return self.results[id]

    def _find_module_non_stub_helper(self, components: List[str],
                                     pkg_dir: str) -> Optional[OnePackageDir]:
        dir_path = pkg_dir
        for index, component in enumerate(components):
            dir_path = os.path.join(dir_path, component)
            if self.fscache.isfile(os.path.join(dir_path, 'py.typed')):
                return os.path.join(pkg_dir, *components[:-1]), index == 0
        return None

    def _update_ns_ancestors(self, components: List[str], match: Tuple[str, bool]) -> None:
        path, verify = match
        for i in range(1, len(components)):
            pkg_id = '.'.join(components[:-i])
            if pkg_id not in self.ns_ancestors and self.fscache.isdir(path):
                self.ns_ancestors[pkg_id] = path
            path = os.path.dirname(path)

    def _find_module(self, id: str) -> Optional[str]:
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
        for pkg_dir in self.search_paths.package_path:
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
                self._update_ns_ancestors(components, non_stub_match)
        if self.options and self.options.use_builtins_fixtures:
            # Everything should be in fixtures.
            third_party_inline_dirs.clear()
            third_party_stubs_dirs.clear()
        python_mypy_path = self.search_paths.mypy_path + self.search_paths.python_path
        candidate_base_dirs = self.find_lib_path_dirs(dir_chain, python_mypy_path) + \
            third_party_stubs_dirs + third_party_inline_dirs + \
            self.find_lib_path_dirs(dir_chain, self.search_paths.typeshed_path)

        # If we're looking for a module like 'foo.bar.baz', then candidate_base_dirs now
        # contains just the subdirectories 'foo/bar' that actually exist under the
        # elements of lib_path.  This is probably much shorter than lib_path itself.
        # Now just look for 'baz.pyi', 'baz/__init__.py', etc., inside those directories.
        seplast = os.sep + components[-1]  # so e.g. '/baz'
        sepinit = os.sep + '__init__'
        near_misses = []  # Collect near misses for namespace mode (see below).
        for base_dir, verify in candidate_base_dirs:
            base_path = base_dir + seplast  # so e.g. '/usr/lib/python3.4/foo/bar/baz'
            # Prefer package over module, i.e. baz/__init__.py* over baz.py*.
            for extension in PYTHON_EXTENSIONS:
                path = base_path + sepinit + extension
                path_stubs = base_path + '-stubs' + sepinit + extension
                if fscache.isfile_case(path):
                    if verify and not verify_module(fscache, id, path):
                        near_misses.append(path)
                        continue
                    return path
                elif fscache.isfile_case(path_stubs):
                    if verify and not verify_module(fscache, id, path_stubs):
                        near_misses.append(path_stubs)
                        continue
                    return path_stubs
                elif self.options and self.options.namespace_packages and fscache.isdir(base_path):
                    near_misses.append(base_path)
            # No package, look for module.
            for extension in PYTHON_EXTENSIONS:
                path = base_path + extension
                if fscache.isfile_case(path):
                    if verify and not verify_module(fscache, id, path):
                        near_misses.append(path)
                        continue
                    return path

        # In namespace mode, re-check those entries that had 'verify'.
        # Assume search path entries xxx, yyy and zzz, and we're
        # looking for foo.bar.baz.  Suppose near_misses has:
        #
        # - xxx/foo/bar/baz.py
        # - yyy/foo/bar/baz/__init__.py
        # - zzz/foo/bar/baz.pyi
        #
        # If any of the foo directories has __init__.py[i], it wins.
        # Else, we look for foo/bar/__init__.py[i], etc.  If there are
        # none, the first hit wins.  Note that this does not take into
        # account whether the lowest-level module is a file (baz.py),
        # a package (baz/__init__.py), or a stub file (baz.pyi) -- for
        # these the first one encountered along the search path wins.
        #
        # The helper function highest_init_level() returns an int that
        # indicates the highest level at which a __init__.py[i] file
        # is found; if no __init__ was found it returns 0, if we find
        # only foo/bar/__init__.py it returns 1, and if we have
        # foo/__init__.py it returns 2 (regardless of what's in
        # foo/bar).  It doesn't look higher than that.
        if self.options and self.options.namespace_packages and near_misses:
            levels = [highest_init_level(fscache, id, path) for path in near_misses]
            index = levels.index(max(levels))
            return near_misses[index]

        # Finally, we may be asked to produce an ancestor for an
        # installed package with a py.typed marker that is a
        # subpackage of a namespace package.  We only fess up to these
        # if we would otherwise return "not found".
        return self.ns_ancestors.get(id)

    def find_modules_recursive(self, module: str) -> List[BuildSource]:
        module_path = self.find_module(module)
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
                    result += self.find_modules_recursive(module + '.' + item)
                elif item != '__init__.py' and item != '__init__.pyi' and \
                        item.endswith(('.py', '.pyi')):
                    mod = item.split('.')[0]
                    if mod not in hits:
                        hits.add(mod)
                        result += self.find_modules_recursive(module + '.' + mod)
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


def highest_init_level(fscache: FileSystemCache, id: str, path: str) -> int:
    """Compute the highest level where an __init__ file is found."""
    if path.endswith(('__init__.py', '__init__.pyi')):
        path = os.path.dirname(path)
    level = 0
    for i in range(id.count('.')):
        path = os.path.dirname(path)
        if any(fscache.isfile_case(os.path.join(path, '__init__{}'.format(extension)))
               for extension in PYTHON_EXTENSIONS):
            level = i + 1
    return level


def mypy_path() -> List[str]:
    path_env = os.getenv('MYPYPATH')
    if not path_env:
        return []
    return path_env.split(os.pathsep)


def default_lib_path(data_dir: str,
                     pyversion: Tuple[int, int],
                     custom_typeshed_dir: Optional[str]) -> List[str]:
    """Return default standard library search paths."""
    # IDEA: Make this more portable.
    path = []  # type: List[str]

    if custom_typeshed_dir:
        typeshed_dir = custom_typeshed_dir
    else:
        auto = os.path.join(data_dir, 'stubs-auto')
        if os.path.isdir(auto):
            data_dir = auto
        typeshed_dir = os.path.join(data_dir, "typeshed")
    if pyversion[0] == 3:
        # We allow a module for e.g. version 3.5 to be in 3.4/. The assumption
        # is that a module added with 3.4 will still be present in Python 3.5.
        versions = ["%d.%d" % (pyversion[0], minor)
                    for minor in reversed(range(PYTHON3_VERSION_MIN[1], pyversion[1] + 1))]
    else:
        # For Python 2, we only have stubs for 2.7
        versions = ["2.7"]
    # E.g. for Python 3.6, try 3.6/, 3.5/, 3.4/, 3/, 2and3/.
    for v in versions + [str(pyversion[0]), '2and3']:
        for lib_type in ['stdlib', 'third_party']:
            stubdir = os.path.join(typeshed_dir, lib_type, v)
            if os.path.isdir(stubdir):
                path.append(stubdir)

    # Add fallback path that can be used if we have a broken installation.
    if sys.platform != 'win32':
        path.append('/usr/local/lib/mypy')
    if not path:
        print("Could not resolve typeshed subdirectories. If you are using mypy\n"
              "from source, you need to run \"git submodule update --init\".\n"
              "Otherwise your mypy install is broken.\nPython executable is located at "
              "{0}.\nMypy located at {1}".format(sys.executable, data_dir), file=sys.stderr)
        sys.exit(1)
    return path


@functools.lru_cache(maxsize=None)
def get_site_packages_dirs(python_executable: Optional[str]) -> Tuple[List[str], List[str]]:
    """Find package directories for given python.

    This runs a subprocess call, which generates a list of the egg directories, and the site
    package directories. To avoid repeatedly calling a subprocess (which can be slow!) we
    lru_cache the results."""
    def make_abspath(path: str, root: str) -> str:
        """Take a path and make it absolute relative to root if not already absolute."""
        if os.path.isabs(path):
            return os.path.normpath(path)
        else:
            return os.path.join(root, os.path.normpath(path))

    if python_executable is None:
        return [], []
    if python_executable == sys.executable:
        # Use running Python's package dirs
        site_packages = sitepkgs.getsitepackages()
    else:
        # Use subprocess to get the package directory of given Python
        # executable
        site_packages = ast.literal_eval(
            subprocess.check_output([python_executable, sitepkgs.__file__],
            stderr=subprocess.PIPE).decode())
    egg_dirs = []
    for dir in site_packages:
        pth = os.path.join(dir, 'easy-install.pth')
        if os.path.isfile(pth):
            with open(pth) as f:
                egg_dirs.extend([make_abspath(d.rstrip(), dir) for d in f.readlines()])
    return egg_dirs, site_packages


def compute_search_paths(sources: List[BuildSource],
                         options: Options,
                         data_dir: str,
                         alt_lib_path: Optional[str] = None) -> SearchPaths:
    """Compute the search paths as specified in PEP 561.

    There are the following 4 members created:
    - User code (from `sources`)
    - MYPYPATH (set either via config or environment variable)
    - installed package directories (which will later be split into stub-only and inline)
    - typeshed
     """
    # Determine the default module search path.
    lib_path = collections.deque(
        default_lib_path(data_dir,
                         options.python_version,
                         custom_typeshed_dir=options.custom_typeshed_dir))

    if options.use_builtins_fixtures:
        # Use stub builtins (to speed up test cases and to make them easier to
        # debug).  This is a test-only feature, so assume our files are laid out
        # as in the source tree.
        root_dir = os.path.dirname(os.path.dirname(__file__))
        lib_path.appendleft(os.path.join(root_dir, 'test-data', 'unit', 'lib-stub'))
    # alt_lib_path is used by some tests to bypass the normal lib_path mechanics.
    # If we don't have one, grab directories of source files.
    python_path = []  # type: List[str]
    if not alt_lib_path:
        for source in sources:
            # Include directory of the program file in the module search path.
            if source.base_dir:
                dir = source.base_dir
                if dir not in python_path:
                    python_path.append(dir)

        # Do this even if running as a file, for sanity (mainly because with
        # multiple builds, there could be a mix of files/modules, so its easier
        # to just define the semantics that we always add the current director
        # to the lib_path
        # TODO: Don't do this in some cases; for motivation see see
        # https://github.com/python/mypy/issues/4195#issuecomment-341915031
        if options.bazel:
            dir = '.'
        else:
            dir = os.getcwd()
        if dir not in lib_path:
            python_path.insert(0, dir)

    # Start with a MYPYPATH environment variable at the front of the mypy_path, if defined.
    mypypath = mypy_path()

    # Add a config-defined mypy path.
    mypypath.extend(options.mypy_path)

    # If provided, insert the caller-supplied extra module path to the
    # beginning (highest priority) of the search path.
    if alt_lib_path:
        mypypath.insert(0, alt_lib_path)

    egg_dirs, site_packages = get_site_packages_dirs(options.python_executable)
    for site_dir in site_packages:
        assert site_dir not in lib_path
        if site_dir in mypypath:
            print("{} is in the MYPYPATH. Please remove it.".format(site_dir), file=sys.stderr)
            sys.exit(1)
        elif site_dir in python_path:
            print("{} is in the PYTHONPATH. Please change directory"
                  " so it is not.".format(site_dir),
                  file=sys.stderr)
            sys.exit(1)

    return SearchPaths(tuple(reversed(python_path)),
                       tuple(mypypath),
                       tuple(egg_dirs + site_packages),
                       tuple(lib_path))
