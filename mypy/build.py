"""Facilities to analyze entire programs, including imported modules.

Parse and analyze the source files of a program in the correct order
(based on file dependencies), and collect the results.

This module only directs a build, which is performed in multiple passes per
file.  The individual passes are implemented in separate modules.

The function build() is the main interface to this module.
"""
# TODO: More consistent terminology, e.g. path/fnam, module/id, state/file

import binascii
import json
import os
import os.path
import sys
import time
from os.path import dirname, basename

from typing import Dict, List, Tuple, Iterable, Union, Optional, NamedTuple

from mypy.types import Type
from mypy.nodes import MypyFile, Node, Import, ImportFrom, ImportAll
from mypy.nodes import MODULE_REF
from mypy.semanal import SemanticAnalyzer, ThirdPass
from mypy.checker import TypeChecker
from mypy.errors import Errors
from mypy import fixup
from mypy.report import Reports
from mypy import defaults
from mypy import moduleinfo
from mypy import util


# We need to know the location of this file to load data, but
# until Python 3.4, __file__ is relative.
__file__ = os.path.realpath(__file__)


# Build targets (for selecting compiler passes)
SEMANTIC_ANALYSIS = 0   # Semantic analysis only
TYPE_CHECK = 1          # Type check


# Build flags
VERBOSE = 'verbose'              # More verbose messages (for troubleshooting)
MODULE = 'module'                # Build module as a script
PROGRAM_TEXT = 'program-text'    # Build command-line argument as a script
TEST_BUILTINS = 'test-builtins'  # Use stub builtins to speed up tests
DUMP_TYPE_STATS = 'dump-type-stats'
DUMP_INFER_STATS = 'dump-infer-stats'
SILENT_IMPORTS = 'silent-imports'  # Silence imports of .py files
FAST_PARSER = 'fast-parser'      # Use experimental fast parser
# Disallow calling untyped functions from typed ones
DISALLOW_UNTYPED_CALLS = 'disallow-untyped-calls'
INCREMENTAL = 'incremental'      # Incremental mode: use the cache

PYTHON_EXTENSIONS = ['.pyi', '.py']


class BuildResult:
    """The result of a successful build.

    Attributes:
      files:  Dictionary from module name to related AST node.
      types:  Dictionary from parse tree node to its inferred type.
    """

    def __init__(self, files: Dict[str, MypyFile],
                 types: Dict[Node, Type]) -> None:
        self.files = files
        self.types = types


class BuildSource:
    def __init__(self, path: Optional[str], module: Optional[str],
            text: Optional[str]) -> None:
        self.path = path
        self.module = module or '__main__'
        self.text = text

    @property
    def effective_path(self) -> str:
        """Return the effective path (ie, <string> if its from in memory)"""
        return self.path or '<string>'


def build(sources: List[BuildSource],
          target: int,
          alt_lib_path: str = None,
          bin_dir: str = None,
          pyversion: Tuple[int, int] = defaults.PYTHON3_VERSION,
          custom_typing_module: str = None,
          implicit_any: bool = False,
          report_dirs: Dict[str, str] = None,
          flags: List[str] = None,
          python_path: bool = False) -> BuildResult:
    """Analyze a program.

    A single call to build performs parsing, semantic analysis and optionally
    type checking for the program *and* all imported modules, recursively.

    Return BuildResult if successful; otherwise raise CompileError.

    Args:
      target: select passes to perform (a build target constant, e.g. C)
      sources: list of sources to build
      alt_lib_dir: an additional directory for looking up library modules
        (takes precedence over other directories)
      bin_dir: directory containing the mypy script, used for finding data
        directories; if omitted, use '.' as the data directory
      pyversion: Python version (major, minor)
      custom_typing_module: if not None, use this module id as an alias for typing
      implicit_any: if True, add implicit Any signatures to all functions
      flags: list of build options (e.g. COMPILE_ONLY)
    """
    report_dirs = report_dirs or {}
    flags = flags or []

    data_dir = default_data_dir(bin_dir)

    find_module_clear_caches()

    # Determine the default module search path.
    lib_path = default_lib_path(data_dir, pyversion, python_path)

    if TEST_BUILTINS in flags:
        # Use stub builtins (to speed up test cases and to make them easier to
        # debug).
        lib_path.insert(0, os.path.join(os.path.dirname(__file__), 'test', 'data', 'lib-stub'))
    else:
        for source in sources:
            if source.path:
                # Include directory of the program file in the module search path.
                lib_path.insert(
                    0, remove_cwd_prefix_from_path(dirname(source.path)))

        # Do this even if running as a file, for sanity (mainly because with
        # multiple builds, there could be a mix of files/modules, so its easier
        # to just define the semantics that we always add the current director
        # to the lib_path
        lib_path.insert(0, os.getcwd())

    # Add MYPYPATH environment variable to front of library path, if defined.
    lib_path[:0] = mypy_path()

    # If provided, insert the caller-supplied extra module path to the
    # beginning (highest priority) of the search path.
    if alt_lib_path:
        lib_path.insert(0, alt_lib_path)

    # TODO: Reports is global to a build manager but only supports a
    # single "main file" Fix this.
    reports = Reports(sources[0].effective_path, data_dir, report_dirs)

    # Construct a build manager object to hold state during the build.
    #
    # Ignore current directory prefix in error messages.
    manager = BuildManager(data_dir, lib_path, target,
                           pyversion=pyversion, flags=flags,
                           ignore_prefix=os.getcwd(),
                           custom_typing_module=custom_typing_module,
                           implicit_any=implicit_any,
                           reports=reports)

    from mypy.depmgr import dispatch
    try:
        dispatch(sources, manager)
        return BuildResult(manager.modules, manager.type_checker.type_map)
    finally:
        manager.log("Build finished with %d modules and %d types" %
                    (len(manager.modules), len(manager.type_checker.type_map)))
        # Finish the HTML or XML reports even if CompileError was raised.
        reports.finish()


def default_data_dir(bin_dir: str) -> str:
    """Returns directory containing typeshed directory

    Args:
      bin_dir: directory containing the mypy script
    """
    if not bin_dir:
        mypy_package = os.path.dirname(__file__)
        parent = os.path.dirname(mypy_package)
        if (os.path.basename(parent) == 'site-packages' or
                os.path.basename(parent) == 'dist-packages'):
            # Installed in site-packages or dist-packages, but invoked with python3 -m mypy;
            # __file__ is .../blah/lib/python3.N/site-packages/mypy/build.py
            # or .../blah/lib/python3.N/dist-packages/mypy/build.py (Debian)
            # or .../blah/lib/site-packages/mypy/build.py (Windows)
            # blah may be a virtualenv or /usr/local.  We want .../blah/lib/mypy.
            lib = parent
            for i in range(2):
                lib = os.path.dirname(lib)
                if os.path.basename(lib) == 'lib':
                    return os.path.join(lib, 'mypy')
        subdir = os.path.join(parent, 'lib', 'mypy')
        if os.path.isdir(subdir):
            # If installed via buildout, the __file__ is
            # somewhere/mypy/__init__.py and what we want is
            # somewhere/lib/mypy.
            return subdir
        # Default to directory containing this file's parent.
        return parent
    base = os.path.basename(bin_dir)
    dir = os.path.dirname(bin_dir)
    if (sys.platform == 'win32' and base.lower() == 'scripts'
            and not os.path.isdir(os.path.join(dir, 'typeshed'))):
        # Installed, on Windows.
        return os.path.join(dir, 'Lib', 'mypy')
    elif base == 'scripts':
        # Assume that we have a repo check out or unpacked source tarball.
        return dir
    elif base == 'bin':
        # Installed to somewhere (can be under /usr/local or anywhere).
        return os.path.join(dir, 'lib', 'mypy')
    elif base == 'python3':
        # Assume we installed python3 with brew on os x
        return os.path.join(os.path.dirname(dir), 'lib', 'mypy')
    else:
        # Don't know where to find the data files!
        raise RuntimeError("Broken installation: can't determine base dir")


def mypy_path() -> List[str]:
    path_env = os.getenv('MYPYPATH')
    if not path_env:
        return []
    return path_env.split(os.pathsep)


def default_lib_path(data_dir: str, pyversion: Tuple[int, int],
        python_path: bool) -> List[str]:
    """Return default standard library search paths."""
    # IDEA: Make this more portable.
    path = []  # type: List[str]

    auto = os.path.join(data_dir, 'stubs-auto')
    if os.path.isdir(auto):
        data_dir = auto

    # We allow a module for e.g. version 3.5 to be in 3.4/. The assumption
    # is that a module added with 3.4 will still be present in Python 3.5.
    versions = ["%d.%d" % (pyversion[0], minor)
                for minor in reversed(range(pyversion[1] + 1))]
    # E.g. for Python 3.2, try 3.2/, 3.1/, 3.0/, 3/, 2and3/.
    # (Note that 3.1 and 3.0 aren't really supported, but we don't care.)
    for v in versions + [str(pyversion[0]), '2and3']:
        for lib_type in ['stdlib', 'third_party']:
            stubdir = os.path.join(data_dir, 'typeshed', lib_type, v)
            if os.path.isdir(stubdir):
                path.append(stubdir)

    # Add fallback path that can be used if we have a broken installation.
    if sys.platform != 'win32':
        path.append('/usr/local/lib/mypy')

    # Contents of Python's sys.path go last, to prefer the stubs
    # TODO: To more closely model what Python actually does, builtins should
    #       go first, then sys.path, then anything in stdlib and third_party.
    if python_path:
        path.extend(sys.path)

    return path


CacheMeta = NamedTuple('CacheMeta',
                       [('id', str),
                        ('path', str),
                        ('mtime', float),
                        ('size', int),
                        ('dependencies', List[str]),
                        ('data_mtime', float),  # mtime of data_json
                        ('data_json', str),  # path of <id>.data.json
                        ])


class BuildManager:
    """This class holds shared state for building a mypy program.

    It is used to coordinate parsing, import processing, semantic
    analysis and type checking.  The actual build steps are carried
    out by dispatch().

    Attributes:
      data_dir:        Mypy data directory (contains stubs)
      target:          Build target; selects which passes to perform
      lib_path:        Library path for looking up modules
      modules:         Mapping of module ID to MypyFile (shared by the passes)
      semantic_analyzer:
                       Semantic analyzer, pass 2
      semantic_analyzer_pass3:
                       Semantic analyzer, pass 3
      type_checker:    Type checker
      errors:          Used for reporting all errors
      pyversion:       Python version (major, minor)
      flags:           Build options
      missing_modules: Set of modules that could not be imported encountered so far
    """

    def __init__(self, data_dir: str,
                 lib_path: List[str],
                 target: int,
                 pyversion: Tuple[int, int],
                 flags: List[str],
                 ignore_prefix: str,
                 custom_typing_module: str,
                 implicit_any: bool,
                 reports: Reports) -> None:
        self.start_time = time.time()
        self.data_dir = data_dir
        self.errors = Errors()
        self.errors.set_ignore_prefix(ignore_prefix)
        self.lib_path = tuple(lib_path)
        self.target = target
        self.pyversion = pyversion
        self.flags = flags
        self.custom_typing_module = custom_typing_module
        self.implicit_any = implicit_any
        self.reports = reports
        self.semantic_analyzer = SemanticAnalyzer(lib_path, self.errors,
                                                  pyversion=pyversion)
        self.modules = self.semantic_analyzer.modules
        self.semantic_analyzer_pass3 = ThirdPass(self.modules, self.errors)
        self.type_checker = TypeChecker(self.errors,
                                        self.modules,
                                        self.pyversion,
                                        DISALLOW_UNTYPED_CALLS in self.flags)
        self.missing_modules = set()  # type: Set[str]

    def all_imported_modules_in_file(self,
                                     file: MypyFile) -> List[Tuple[str, int]]:
        """Find all reachable import statements in a file.

        Return list of tuples (module id, import line number) for all modules
        imported in file.
        """
        def correct_rel_imp(imp: Union[ImportFrom, ImportAll]) -> str:
            """Function to correct for relative imports."""
            file_id = file.fullname()
            rel = imp.relative
            if rel == 0:
                return imp.id
            if os.path.basename(file.path).startswith('__init__.'):
                rel -= 1
            if rel != 0:
                file_id = ".".join(file_id.split(".")[:-rel])
            new_id = file_id + "." + imp.id if imp.id else file_id

            return new_id

        res = []  # type: List[Tuple[str, int]]
        for imp in file.imports:
            if not imp.is_unreachable:
                if isinstance(imp, Import):
                    for id, _ in imp.ids:
                        res.append((id, imp.line))
                elif isinstance(imp, ImportFrom):
                    cur_id = correct_rel_imp(imp)
                    res.append((cur_id, imp.line))
                    # Also add any imported names that are submodules.
                    for name, __ in imp.names:
                        sub_id = cur_id + '.' + name
                        if self.is_module(sub_id):
                            res.append((sub_id, imp.line))
                elif isinstance(imp, ImportAll):
                    res.append((correct_rel_imp(imp), imp.line))
        return res

    def is_module(self, id: str) -> bool:
        """Is there a file in the file system corresponding to module id?"""
        return find_module(id, self.lib_path) is not None

    def module_not_found(self, path: str, line: int, id: str) -> None:
        self.errors.set_file(path)
        stub_msg = "(Stub files are from https://github.com/python/typeshed)"
        if ((self.pyversion[0] == 2 and moduleinfo.is_py2_std_lib_module(id)) or
                (self.pyversion[0] >= 3 and moduleinfo.is_py3_std_lib_module(id))):
            self.errors.report(
                line, "No library stub file for standard library module '{}'".format(id))
            self.errors.report(line, stub_msg, severity='note', only_once=True)
        elif moduleinfo.is_third_party_module(id):
            self.errors.report(line, "No library stub file for module '{}'".format(id))
            self.errors.report(line, stub_msg, severity='note', only_once=True)
        else:
            self.errors.report(line, "Cannot find module named '{}'".format(id))
            self.errors.report(line, "(Perhaps setting MYPYPATH would help)", severity='note',
                               only_once=True)

    def log(self, *message: str) -> None:
        if VERBOSE in self.flags:
            print('%.3f:LOG: ' % (time.time() - self.start_time), *message, file=sys.stderr)
            sys.stderr.flush()

    def trace(self, *message: str) -> None:
        if self.flags.count(VERBOSE) >= 2:
            print('%.3f:TRACE:' % (time.time() - self.start_time), *message, file=sys.stderr)
            sys.stderr.flush()


def remove_cwd_prefix_from_path(p: str) -> str:
    """Remove current working directory prefix from p, if present.

    Also crawl up until a directory without __init__.py is found.

    If the result would be empty, return '.' instead.
    """
    cur = os.getcwd()
    # Add separator to the end of the path, unless one is already present.
    if basename(cur) != '':
        cur += os.sep
    # Compute root path.
    while p and os.path.isfile(os.path.join(p, '__init__.py')):
        dir, base = os.path.split(p)
        if not base:
            break
        p = dir
    # Remove current directory prefix from the path, if present.
    if p.startswith(cur):
        p = p[len(cur):]
    # Avoid returning an empty path; replace that with '.'.
    if p == '':
        p = '.'
    return p


# TODO: Maybe move this into BuildManager?
# Cache find_module: (id, lib_path) -> result.
find_module_cache = {}  # type: Dict[Tuple[str, Tuple[str, ...]], str]

# Cache some repeated work within distinct find_module calls: finding which
# elements of lib_path have even the subdirectory they'd need for the module
# to exist.  This is shared among different module ids when they differ only
# in the last component.
find_module_dir_cache = {}  # type: Dict[Tuple[str, Tuple[str, ...]], List[str]]


def find_module_clear_caches():
    find_module_cache.clear()
    find_module_dir_cache.clear()


def find_module(id: str, lib_path: Iterable[str]) -> str:
    """Return the path of the module source file, or None if not found."""
    if not isinstance(lib_path, tuple):
        lib_path = tuple(lib_path)

    def find():
        # If we're looking for a module like 'foo.bar.baz', it's likely that most of the
        # many elements of lib_path don't even have a subdirectory 'foo/bar'.  Discover
        # that only once and cache it for when we look for modules like 'foo.bar.blah'
        # that will require the same subdirectory.
        components = id.split('.')
        dir_chain = os.sep.join(components[:-1])  # e.g., 'foo/bar'
        if (dir_chain, lib_path) not in find_module_dir_cache:
            dirs = []
            for pathitem in lib_path:
                # e.g., '/usr/lib/python3.4/foo/bar'
                dir = os.path.normpath(os.path.join(pathitem, dir_chain))
                if os.path.isdir(dir):
                    dirs.append(dir)
            find_module_dir_cache[dir_chain, lib_path] = dirs
        candidate_base_dirs = find_module_dir_cache[dir_chain, lib_path]

        # If we're looking for a module like 'foo.bar.baz', then candidate_base_dirs now
        # contains just the subdirectories 'foo/bar' that actually exist under the
        # elements of lib_path.  This is probably much shorter than lib_path itself.
        # Now just look for 'baz.pyi', 'baz/__init__.py', etc., inside those directories.
        seplast = os.sep + components[-1]  # so e.g. '/baz'
        sepinit = os.sep + '__init__'
        for base_dir in candidate_base_dirs:
            base_path = base_dir + seplast  # so e.g. '/usr/lib/python3.4/foo/bar/baz'
            for extension in PYTHON_EXTENSIONS:
                path = base_path + extension
                if not os.path.isfile(path):
                    path = base_path + sepinit + extension
                if os.path.isfile(path) and verify_module(id, path):
                    return path
        return None

    key = (id, lib_path)
    if key not in find_module_cache:
        find_module_cache[key] = find()
    return find_module_cache[key]


def find_modules_recursive(module: str, lib_path: List[str]) -> List[BuildSource]:
    module_path = find_module(module, lib_path)
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
        for item in sorted(os.listdir(os.path.dirname(module_path))):
            abs_path = os.path.join(os.path.dirname(module_path), item)
            if os.path.isdir(abs_path) and \
                    (os.path.isfile(os.path.join(abs_path, '__init__.py')) or
                    os.path.isfile(os.path.join(abs_path, '__init__.pyi'))):
                hits.add(item)
                result += find_modules_recursive(module + '.' + item, lib_path)
            elif item != '__init__.py' and item != '__init__.pyi' and \
                    item.endswith(('.py', '.pyi')):
                mod = item.split('.')[0]
                if mod not in hits:
                    hits.add(mod)
                    result += find_modules_recursive(
                        module + '.' + mod, lib_path)
    return result


def verify_module(id: str, path: str) -> bool:
    """Check that all packages containing id have a __init__ file."""
    if path.endswith(('__init__.py', '__init__.pyi')):
        path = dirname(path)
    for i in range(id.count('.')):
        path = dirname(path)
        if not any(os.path.isfile(os.path.join(path, '__init__{}'.format(extension)))
                   for extension in PYTHON_EXTENSIONS):
            return False
    return True


def read_with_python_encoding(path: str, pyversion: Tuple[int, int]) -> str:
    """Read the Python file with while obeying PEP-263 encoding detection"""
    source_bytearray = bytearray()
    encoding = 'utf8' if pyversion[0] >= 3 else 'ascii'

    with open(path, 'rb') as f:
        # read first two lines and check if PEP-263 coding is present
        source_bytearray.extend(f.readline())
        source_bytearray.extend(f.readline())

        # check for BOM UTF-8 encoding and strip it out if present
        if source_bytearray.startswith(b'\xef\xbb\xbf'):
            encoding = 'utf8'
            source_bytearray = source_bytearray[3:]
        else:
            _encoding, _ = util.find_python_encoding(source_bytearray, pyversion)
            # check that the coding isn't mypy. We skip it since
            # registering may not have happened yet
            if _encoding != 'mypy':
                encoding = _encoding

        source_bytearray.extend(f.read())
        return source_bytearray.decode(encoding)


MYPY_CACHE = '.mypy_cache'


def get_cache_names(id: str, path: str, pyversion: Tuple[int, int]) -> Tuple[str, str]:
    prefix = os.path.join(MYPY_CACHE, '%d.%d' % pyversion, *id.split('.'))
    is_package = os.path.basename(path).startswith('__init__.py')
    if is_package:
        prefix = os.path.join(prefix, '__init__')
    return (prefix + '.meta.json', prefix + '.data.json')


def find_cache_meta(id: str, path: str, manager: BuildManager) -> Optional[CacheMeta]:
    meta_json, data_json = get_cache_names(id, path, manager.pyversion)
    manager.trace('Looking for {} {}'.format(id, data_json))
    if not os.path.exists(meta_json):
        return None
    with open(meta_json, 'r') as f:
        meta_str = f.read()
        manager.trace('Meta {} {}'.format(id, meta_str.rstrip()))
        meta = json.loads(meta_str)  # TODO: Errors
    if not isinstance(meta, dict):
        return None
    path = os.path.abspath(path)
    m = CacheMeta(
        meta.get('id'),
        meta.get('path'),
        meta.get('mtime'),
        meta.get('size'),
        meta.get('dependencies'),
        meta.get('data_mtime'),
        data_json,
    )
    if (m.id != id or m.path != path or
            m.mtime is None or m.size is None or
            m.dependencies is None or m.data_mtime is None):
        return None
    # TODO: Share stat() outcome with find_module()
    st = os.stat(path)  # TODO: Errors
    if st.st_mtime != m.mtime or st.st_size != m.size:
        manager.log('Metadata abandoned because of modified file {}'.format(path))
        return None
    # It's a match on (id, path, mtime, size).
    # Check data_json; assume if its mtime matches it's good.
    # TODO: stat() errors
    if os.path.getmtime(data_json) != m.data_mtime:
        return None
    manager.log('Found {} {}'.format(id, meta_json))
    return m


def random_string():
    return binascii.hexlify(os.urandom(8)).decode('ascii')


def write_cache(id: str, path: str, tree: MypyFile, dependencies: List[str],
                manager: BuildManager) -> None:
    path = os.path.abspath(path)
    manager.trace('Dumping {} {}'.format(id, path))
    st = os.stat(path)  # TODO: Errors
    mtime = st.st_mtime
    size = st.st_size
    meta_json, data_json = get_cache_names(id, path, manager.pyversion)
    manager.log('Writing {} {} {}'.format(id, meta_json, data_json))
    data = tree.serialize()
    parent = os.path.dirname(data_json)
    if not os.path.isdir(parent):
        os.makedirs(parent)
    assert os.path.dirname(meta_json) == parent
    nonce = '.' + random_string()
    data_json_tmp = data_json + nonce
    meta_json_tmp = meta_json + nonce
    with open(data_json_tmp, 'w') as f:
        json.dump(data, f, indent=2, sort_keys=True)
        f.write('\n')
    data_mtime = os.path.getmtime(data_json_tmp)
    meta = {'id': id,
            'path': path,
            'mtime': mtime,
            'size': size,
            'data_mtime': data_mtime,
            'dependencies': dependencies,
            }
    with open(meta_json_tmp, 'w') as f:
        json.dump(meta, f, sort_keys=True)
        f.write('\n')
    os.rename(data_json_tmp, data_json)
    os.rename(meta_json_tmp, meta_json)

    return

    # Now, as a test, read it back.
    print()
    print('Reading what we wrote for', id, 'from', data_json)
    with open(data_json, 'r') as f:
        new_data = json.load(f)
    assert new_data == data
    new_tree = MypyFile.deserialize(new_data)
    new_names = new_tree.names
    new_keys = sorted(new_names)

    print('Fixing up', id)
    fixup.fixup_module_pass_one(new_tree, manager.modules)

    print('Comparing keys', id)
    old_tree = tree
    old_names = old_tree.names
    old_keys = sorted(old_names)
    if new_keys != old_keys:
        for key in new_keys:
            if key not in old_keys:
                print('  New key', key, 'not found in old tree')
        for key in old_keys:
            if key not in new_keys:
                v = old_names[key]
                if key != '__builtins__' and v.module_public:
                    print('  Old key', key, 'not found in new tree')

    print('Comparing values', id)
    modules = manager.modules
    for key in old_keys:
        if key not in new_keys:
            continue
        oldv = old_names[key]
        newv = new_names[key]
        if newv.mod_id != oldv.mod_id:
            newv.mod_id = id  # XXX Hack
        if newv.kind == MODULE_REF and newv.node is None:
            fn = oldv.node.fullname()
            if fn in modules:
                newv.node = modules[fn]
            else:
                print('*** Cannot fix up reference to module', fn, 'for', key)
        if str(oldv) != str(newv):
            print(' ', key, 'old', oldv)
            print(' ', ' ' * len(key), 'new', newv)
            import pdb  # type: ignore
            pdb.set_trace()
            print()
