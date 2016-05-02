"""Facilities to analyze entire programs, including imported modules.

Parse and analyze the source files of a program in the correct order
(based on file dependencies), and collect the results.

This module only directs a build, which is performed in multiple passes per
file.  The individual passes are implemented in separate modules.

The function build() is the main interface to this module.
"""
# TODO: More consistent terminology, e.g. path/fnam, module/id, state/file

import binascii
import collections
import contextlib
import json
import os
import os.path
import sys
import time
from os.path import dirname, basename

from typing import (AbstractSet, Dict, Iterable, Iterator, List,
                    NamedTuple, Optional, Set, Tuple, Union)

from mypy.types import Type
from mypy.nodes import (MypyFile, Node, Import, ImportFrom, ImportAll,
                        SymbolTableNode, MODULE_REF)
from mypy.semanal import FirstPass, SemanticAnalyzer, ThirdPass
from mypy.checker import TypeChecker
from mypy.errors import Errors, CompileError, report_internal_error
from mypy import fixup
from mypy.report import Reports
from mypy import defaults
from mypy import moduleinfo
from mypy import util
from mypy.fixup import fixup_module_pass_one, fixup_module_pass_two
from mypy.parse import parse
from mypy.stats import dump_type_stats


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
ALMOST_SILENT = 'almost-silent'  # If SILENT_IMPORTS: report silenced imports as errors
INCREMENTAL = 'incremental'      # Incremental mode: use the cache
FAST_PARSER = 'fast-parser'      # Use experimental fast parser
# Disallow calling untyped functions from typed ones
DISALLOW_UNTYPED_CALLS = 'disallow-untyped-calls'
# Disallow defining untyped (or incompletely typed) functions
DISALLOW_UNTYPED_DEFS = 'disallow-untyped-defs'
# Type check unannotated functions
CHECK_UNTYPED_DEFS = 'check-untyped-defs'

PYTHON_EXTENSIONS = ['.pyi', '.py']


class BuildResult:
    """The result of a successful build.

    Attributes:
      manager: The build manager.
      files:   Dictionary from module name to related AST node.
      types:   Dictionary from parse tree node to its inferred type.
      errors:  List of error messages.
    """

    def __init__(self, manager: 'BuildManager') -> None:
        self.manager = manager
        self.files = manager.modules
        self.types = manager.type_checker.type_map
        self.errors = manager.errors.messages()


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


class BuildSourceSet:
    """Efficiently test a file's membership in the set of build sources."""

    def __init__(self, sources: List[BuildSource]) -> None:
        self.source_text_present = False
        self.source_modules = set()  # type: Set[str]
        self.source_paths = set()  # type: Set[str]

        for source in sources:
            if source.text is not None:
                self.source_text_present = True
            elif source.path:
                self.source_paths.add(source.path)
            else:
                self.source_modules.add(source.module)

    def is_source(self, file: MypyFile) -> bool:
        if file.path and file.path in self.source_paths:
            return True
        elif file._fullname in self.source_modules:
            return True
        elif file.path is None and self.source_text_present:
            return True
        else:
            return False


def build(sources: List[BuildSource],
          target: int,
          alt_lib_path: str = None,
          bin_dir: str = None,
          pyversion: Tuple[int, int] = defaults.PYTHON3_VERSION,
          custom_typing_module: str = None,
          report_dirs: Dict[str, str] = None,
          flags: List[str] = None,
          python_path: bool = False) -> BuildResult:
    """Analyze a program.

    A single call to build performs parsing, semantic analysis and optionally
    type checking for the program *and* all imported modules, recursively.

    Return BuildResult if successful or only non-blocking errors were found;
    otherwise raise CompileError.

    Args:
      target: select passes to perform (a build target constant, e.g. C)
      sources: list of sources to build
      alt_lib_path: an additional directory for looking up library modules
        (takes precedence over other directories)
      bin_dir: directory containing the mypy script, used for finding data
        directories; if omitted, use '.' as the data directory
      pyversion: Python version (major, minor)
      custom_typing_module: if not None, use this module id as an alias for typing
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
                dir = remove_cwd_prefix_from_path(dirname(source.path))
                if dir not in lib_path:
                    lib_path.insert(0, dir)

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

    reports = Reports(data_dir, report_dirs)

    source_set = BuildSourceSet(sources)

    # Construct a build manager object to hold state during the build.
    #
    # Ignore current directory prefix in error messages.
    manager = BuildManager(data_dir, lib_path, target,
                           pyversion=pyversion, flags=flags,
                           ignore_prefix=os.getcwd(),
                           custom_typing_module=custom_typing_module,
                           source_set=source_set,
                           reports=reports)

    try:
        dispatch(sources, manager)
        return BuildResult(manager)
    finally:
        manager.log("Build finished with %d modules, %d types, and %d errors" %
                    (len(manager.modules),
                     len(manager.type_checker.type_map),
                     manager.errors.num_messages()))
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
    elif dir.endswith('python-exec'):
        # Gentoo uses a python wrapper in /usr/lib to which mypy is a symlink.
        return os.path.join(os.path.dirname(dir), 'mypy')
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
                        ('dependencies', List[str]),  # names of imported modules
                        ('data_mtime', float),  # mtime of data_json
                        ('data_json', str),  # path of <id>.data.json
                        ('suppressed', List[str]),  # dependencies that weren't imported
                        ])
# NOTE: dependencies + suppressed == all unreachable imports;
# suppressed contains those reachable imports that were prevented by
# --silent-imports or simply not found.


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
                 source_set: BuildSourceSet,
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
        self.source_set = source_set
        self.reports = reports
        check_untyped_defs = CHECK_UNTYPED_DEFS in self.flags
        self.semantic_analyzer = SemanticAnalyzer(lib_path, self.errors,
                                                  pyversion=pyversion,
                                                  check_untyped_defs=check_untyped_defs)
        self.modules = self.semantic_analyzer.modules
        self.semantic_analyzer_pass3 = ThirdPass(self.modules, self.errors)
        self.type_checker = TypeChecker(self.errors,
                                        self.modules,
                                        self.pyversion,
                                        DISALLOW_UNTYPED_CALLS in self.flags,
                                        DISALLOW_UNTYPED_DEFS in self.flags,
                                        check_untyped_defs)
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
                    pos = len(res)
                    all_are_submodules = True
                    # Also add any imported names that are submodules.
                    for name, __ in imp.names:
                        sub_id = cur_id + '.' + name
                        if self.is_module(sub_id):
                            res.append((sub_id, imp.line))
                        else:
                            all_are_submodules = False
                    # If all imported names are submodules, don't add
                    # cur_id as a dependency.  Otherwise (i.e., if at
                    # least one imported name isn't a submodule)
                    # cur_id is also a dependency, and we should
                    # insert it *before* any submodules.
                    if not all_are_submodules:
                        res.insert(pos, ((cur_id, imp.line)))
                elif isinstance(imp, ImportAll):
                    res.append((correct_rel_imp(imp), imp.line))
        return res

    def is_module(self, id: str) -> bool:
        """Is there a file in the file system corresponding to module id?"""
        return find_module(id, self.lib_path) is not None

    def parse_file(self, id: str, path: str, source: str) -> MypyFile:
        """Parse the source of a file with the given name.

        Raise CompileError if there is a parse error.
        """
        num_errs = self.errors.num_messages()
        tree = parse(source, path, self.errors,
                     pyversion=self.pyversion,
                     custom_typing_module=self.custom_typing_module,
                     fast_parser=FAST_PARSER in self.flags)
        tree._fullname = id
        if self.errors.num_messages() != num_errs:
            self.log("Bailing due to parse errors")
            self.errors.raise_error()
        return tree

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
            self.errors.report(line, '(Perhaps setting MYPYPATH '
                                     'or using the "--silent-imports" flag would help)',
                               severity='note', only_once=True)

    def report_file(self, file: MypyFile) -> None:
        if self.source_set.is_source(file):
            self.reports.file(file, type_map=self.type_checker.type_map)

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
    while (p and
           (os.path.isfile(os.path.join(p, '__init__.py')) or
            os.path.isfile(os.path.join(p, '__init__.pyi')))):
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
    """Return the file names for the cache files.

    Args:
      id: module ID
      path: module path (used to recognize packages)
      pyversion: Python version (major, minor)

    Returns:
      A tuple with the file names to be used for the meta JSON and the
      data JSON, respectively.
    """
    prefix = os.path.join(MYPY_CACHE, '%d.%d' % pyversion, *id.split('.'))
    is_package = os.path.basename(path).startswith('__init__.py')
    if is_package:
        prefix = os.path.join(prefix, '__init__')
    return (prefix + '.meta.json', prefix + '.data.json')


def find_cache_meta(id: str, path: str, manager: BuildManager) -> Optional[CacheMeta]:
    """Find cache data for a module.

    Args:
      id: module ID
      path: module path
      manager: the build manager (for pyversion, log/trace, and build options)

    Returns:
      A CacheMeta instance if the cache data was found and appears
      valid; otherwise None.
    """
    # TODO: May need to take more build options into account; in
    # particular SILENT_IMPORTS may affect the cache dramatically.
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
        meta.get('dependencies', []),
        meta.get('data_mtime'),
        data_json,
        meta.get('suppressed', []),
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


def write_cache(id: str, path: str, tree: MypyFile,
                dependencies: List[str], suppressed: List[str],
                manager: BuildManager) -> None:
    """Write cache files for a module.

    Args:
      id: module ID
      path: module path
      tree: the fully checked module data
      dependencies: module IDs on which this module depends
      suppressed: module IDs which were suppressed as dependencies
      manager: the build manager (for pyversion, log/trace)
    """
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
            'suppressed': suppressed,
            }
    with open(meta_json_tmp, 'w') as f:
        json.dump(meta, f, sort_keys=True)
        f.write('\n')
    # TODO: On Windows, os.rename() may not be atomic, and we could
    # use os.replace().  However that's new in Python 3.3.
    os.rename(data_json_tmp, data_json)
    os.rename(meta_json_tmp, meta_json)


"""Dependency manager.

Design
======

Ideally
-------

A. Collapse cycles (each SCC -- strongly connected component --
   becomes one "supernode").

B. Topologically sort nodes based on dependencies.

C. Process from leaves towards roots.

Wrinkles
--------

a. Need to parse source modules to determine dependencies.

b. Processing order for modules within an SCC.

c. Must order mtimes of files to decide whether to re-process; depends
   on clock never resetting.

d. from P import M; checks filesystem whether module P.M exists in
   filesystem.

e. Race conditions, where somebody modifies a file while we're
   processing.  I propose not to modify the algorithm to handle this,
   but to detect when this could lead to inconsistencies.  (For
   example, when we decide on the dependencies based on cache
   metadata, and then we decide to re-parse a file because of a stale
   dependency, if the re-parsing leads to a different list of
   dependencies we should warn the user or start over.)

Steps
-----

1. For each explicitly given module find the source file location.

2. For each such module load and check the cache metadata, and decide
   whether it's valid.

3. Now recursively (or iteratively) find dependencies and add those to
   the graph:

   - for cached nodes use the list of dependencies from the cache
     metadata (this will be valid even if we later end up re-parsing
     the same source);

   - for uncached nodes parse the file and process all imports found,
     taking care of (a) above.

Step 3 should also address (d) above.

Once step 3 terminates we have the entire dependency graph, and for
each module we've either loaded the cache metadata or parsed the
source code.  (However, we may still need to parse those modules for
which we have cache metadata but that depend, directly or indirectly,
on at least one module for which the cache metadata is stale.)

Now we can execute steps A-C from the first section.  Finding SCCs for
step A shouldn't be hard; there's a recipe here:
http://code.activestate.com/recipes/578507/.  There's also a plethora
of topsort recipes, e.g. http://code.activestate.com/recipes/577413/.

For single nodes, processing is simple.  If the node was cached, we
deserialize the cache data and fix up cross-references.  Otherwise, we
do semantic analysis followed by type checking.  We also handle (c)
above; if a module has valid cache data *but* any of its
dependendencies was processed from source, then the module should be
processed from source.

A relatively simple optimization (outside SCCs) we might do in the
future is as follows: if a node's cache data is valid, but one or more
of its dependencies are out of date so we have to re-parse the node
from source, once we have fully type-checked the node, we can decide
whether its symbol table actually changed compared to the cache data
(by reading the cache data and comparing it to the data we would be
writing).  If there is no change we can declare the node up to date,
and any node that depends (and for which we have cached data, and
whose other dependencies are up to date) on it won't need to be
re-parsed from source.

Import cycles
-------------

Finally we have to decide how to handle (c), import cycles.  Here
we'll need a modified version of the original state machine
(build.py), but we only need to do this per SCC, and we won't have to
deal with changes to the list of nodes while we're processing it.

If all nodes in the SCC have valid cache metadata and all dependencies
outside the SCC are still valid, we can proceed as follows:

  1. Load cache data for all nodes in the SCC.

  2. Fix up cross-references for all nodes in the SCC.

Otherwise, the simplest (but potentially slow) way to proceed is to
invalidate all cache data in the SCC and re-parse all nodes in the SCC
from source.  We can do this as follows:

  1. Parse source for all nodes in the SCC.

  2. Semantic analysis for all nodes in the SCC.

  3. Type check all nodes in the SCC.

(If there are more passes the process is the same -- each pass should
be done for all nodes before starting the next pass for any nodes in
the SCC.)

We could process the nodes in the SCC in any order.  For sentimental
reasons, I've decided to process them in the reverse order in which we
encountered them when originally constructing the graph.  That's how
the old build.py deals with cycles, and at least this reproduces the
previous implementation more accurately.

Can we do better than re-parsing all nodes in the SCC when any of its
dependencies are out of date?  It's doubtful.  The optimization
mentioned at the end of the previous section would require re-parsing
and type-checking a node and then comparing its symbol table to the
cached data; but because the node is part of a cycle we can't
technically type-check it until the semantic analysis of all other
nodes in the cycle has completed.  (This is an important issue because
Dropbox has a very large cycle in production code.  But I'd like to
deal with it later.)

Additional wrinkles
-------------------

During implementation more wrinkles were found.

- When a submodule of a package (e.g. x.y) is encountered, the parent
  package (e.g. x) must also be loaded, but it is not strictly a
  dependency.  See State.add_ancestors() below.
"""


class ModuleNotFound(Exception):
    """Control flow exception to signal that a module was not found."""


class State:
    """The state for a module.

    The source is only used for the -c command line option; in that
    case path is None.  Otherwise source is None and path isn't.
    """

    manager = None  # type: BuildManager
    order_counter = 0  # Class variable
    order = None  # type: int  # Order in which modules were encountered
    id = None  # type: str  # Fully qualified module name
    path = None  # type: Optional[str]  # Path to module source
    xpath = None  # type: str  # Path or '<string>'
    source = None  # type: Optional[str]  # Module source code
    meta = None  # type: Optional[CacheMeta]
    data = None  # type: Optional[str]
    tree = None  # type: Optional[MypyFile]
    dependencies = None  # type: List[str]
    suppressed = None  # type: List[str]  # Suppressed/missing dependencies

    # Map each dependency to the line number where it is first imported
    dep_line_map = None  # type: Dict[str, int]

    # Parent package, its parent, etc.
    ancestors = None  # type: Optional[List[str]]

    # List of (path, line number) tuples giving context for import
    import_context = None  # type: List[Tuple[str, int]]

    # The State from which this module was imported, if any
    caller_state = None  # type: Optional[State]

    # If caller_state is set, the line number in the caller where the import occurred
    caller_line = 0

    def __init__(self,
                 id: Optional[str],
                 path: Optional[str],
                 source: Optional[str],
                 manager: BuildManager,
                 caller_state: 'State' = None,
                 caller_line: int = 0,
                 ancestor_for: 'State' = None,
                 ) -> None:
        assert id or path or source is not None, "Neither id, path nor source given"
        self.manager = manager
        State.order_counter += 1
        self.order = State.order_counter
        self.caller_state = caller_state
        self.caller_line = caller_line
        if caller_state:
            self.import_context = caller_state.import_context[:]
            self.import_context.append((caller_state.xpath, caller_line))
        else:
            self.import_context = []
        self.id = id or '__main__'
        if not path and source is None:
            file_id = id
            if id == 'builtins' and manager.pyversion[0] == 2:
                # The __builtin__ module is called internally by mypy
                # 'builtins' in Python 2 mode (similar to Python 3),
                # but the stub file is __builtin__.pyi.  The reason is
                # that a lot of code hard-codes 'builtins.x' and it's
                # easier to work it around like this.  It also means
                # that the implementation can mostly ignore the
                # difference and just assume 'builtins' everywhere,
                # which simplifies code.
                file_id = '__builtin__'
            path = find_module(file_id, manager.lib_path)
            if path:
                # In silent mode, don't import .py files, except from stubs.
                if (SILENT_IMPORTS in manager.flags and
                        path.endswith('.py') and (caller_state or ancestor_for)):
                    # (Never silence builtins, even if it's a .py file;
                    # this can happen in tests!)
                    if (id != 'builtins' and
                        not ((caller_state and
                              caller_state.tree and
                              caller_state.tree.is_stub))):
                        if ALMOST_SILENT in manager.flags:
                            if ancestor_for:
                                self.skipping_ancestor(id, path, ancestor_for)
                            else:
                                self.skipping_module(id, path)
                        path = None
                        manager.missing_modules.add(id)
                        raise ModuleNotFound
            else:
                # Could not find a module.  Typically the reason is a
                # misspelled module name, missing stub, module not in
                # search path or the module has not been installed.
                if caller_state:
                    suppress_message = ((SILENT_IMPORTS in manager.flags and
                                        ALMOST_SILENT not in manager.flags) or
                                        (caller_state.tree is not None and
                                         (caller_line in caller_state.tree.ignored_lines or
                                          'import' in caller_state.tree.weak_opts)))
                    if not suppress_message:
                        save_import_context = manager.errors.import_context()
                        manager.errors.set_import_context(caller_state.import_context)
                        manager.module_not_found(caller_state.xpath, caller_line, id)
                        manager.errors.set_import_context(save_import_context)
                    manager.missing_modules.add(id)
                    raise ModuleNotFound
                else:
                    # If we can't find a root source it's always fatal.
                    # TODO: This might hide non-fatal errors from
                    # root sources processed earlier.
                    raise CompileError(["mypy: can't find module '%s'" % id])
        self.path = path
        self.xpath = path or '<string>'
        self.source = source
        if path and source is None and INCREMENTAL in manager.flags:
            self.meta = find_cache_meta(self.id, self.path, manager)
            # TODO: Get mtime if not cached.
        self.add_ancestors()
        if self.meta:
            # Make copies, since we may modify these and want to
            # compare them to the originals later.
            self.dependencies = list(self.meta.dependencies)
            self.suppressed = list(self.meta.suppressed)
            self.dep_line_map = {}
        else:
            # Parse the file (and then some) to get the dependencies.
            self.parse_file()
            self.suppressed = []

    def skipping_ancestor(self, id: str, path: str, ancestor_for: 'State') -> None:
        # TODO: Read the path (the __init__.py file) and return
        # immediately if it's empty or only contains comments.
        # But beware, some package may be the ancestor of many modules,
        # so we'd need to cache the decision.
        manager = self.manager
        manager.errors.set_import_context([])
        manager.errors.set_file(ancestor_for.xpath)
        manager.errors.report(-1, "Ancestor package '%s' silently ignored" % (id,),
                              severity='note', only_once=True)
        manager.errors.report(-1, "(Using --silent-imports, submodule passed on command line)",
                              severity='note', only_once=True)
        manager.errors.report(-1, "(This note brought to you by --almost-silent)",
                              severity='note', only_once=True)

    def skipping_module(self, id: str, path: str) -> None:
        assert self.caller_state, (id, path)
        manager = self.manager
        save_import_context = manager.errors.import_context()
        manager.errors.set_import_context(self.caller_state.import_context)
        manager.errors.set_file(self.caller_state.xpath)
        line = self.caller_line
        manager.errors.report(line, "Import of '%s' silently ignored" % (id,),
                              severity='note')
        manager.errors.report(line, "(Using --silent-imports, module not passed on command line)",
                              severity='note', only_once=True)
        manager.errors.report(line, "(This note courtesy of --almost-silent)",
                              severity='note', only_once=True)
        manager.errors.set_import_context(save_import_context)

    def add_ancestors(self) -> None:
        # All parent packages are new ancestors.
        ancestors = []
        parent = self.id
        while '.' in parent:
            parent, _ = parent.rsplit('.', 1)
            ancestors.append(parent)
        self.ancestors = ancestors

    def is_fresh(self) -> bool:
        """Return whether the cache data for this file is fresh."""
        # NOTE: self.dependencies may differ from
        # self.meta.dependencies when a dependency is dropped due to
        # suppression by --silent-imports.  However when a suppressed
        # dependency is added back we find out later in the process.
        return self.meta is not None and self.dependencies == self.meta.dependencies

    def mark_stale(self) -> None:
        """Throw away the cache data for this file, marking it as stale."""
        self.meta = None

    def check_blockers(self) -> None:
        """Raise CompileError if a blocking error is detected."""
        if self.manager.errors.is_blockers():
            self.manager.log("Bailing due to blocking errors")
            self.manager.errors.raise_error()

    @contextlib.contextmanager
    def wrap_context(self) -> Iterator[None]:
        save_import_context = self.manager.errors.import_context()
        self.manager.errors.set_import_context(self.import_context)
        try:
            yield
        except CompileError:
            raise
        except Exception as err:
            report_internal_error(err, self.path, 0)
        self.manager.errors.set_import_context(save_import_context)
        self.check_blockers()

    # Methods for processing cached modules.

    def load_tree(self) -> None:
        with open(self.meta.data_json) as f:
            data = json.load(f)
        # TODO: Assert data file wasn't changed.
        self.tree = MypyFile.deserialize(data)
        self.manager.modules[self.id] = self.tree

    def fix_cross_refs(self) -> None:
        fixup_module_pass_one(self.tree, self.manager.modules)

    def calculate_mros(self) -> None:
        fixup_module_pass_two(self.tree, self.manager.modules)

    # Methods for processing modules from source code.

    def parse_file(self) -> None:
        if self.tree is not None:
            # The file was already parsed (in __init__()).
            return

        manager = self.manager
        modules = manager.modules
        manager.log("Parsing %s (%s)" % (self.xpath, self.id))

        with self.wrap_context():
            source = self.source
            self.source = None  # We won't need it again.
            if self.path and source is None:
                try:
                    source = read_with_python_encoding(self.path, manager.pyversion)
                except IOError as ioerr:
                    raise CompileError([
                        "mypy: can't read file '{}': {}".format(self.path, ioerr.strerror)])
                except UnicodeDecodeError as decodeerr:
                    raise CompileError([
                        "mypy: can't decode file '{}': {}".format(self.path, str(decodeerr))])
            self.tree = manager.parse_file(self.id, self.xpath, source)

        modules[self.id] = self.tree

        # Do the first pass of semantic analysis: add top-level
        # definitions in the file to the symbol table.  We must do
        # this before processing imports, since this may mark some
        # import statements as unreachable.
        first = FirstPass(manager.semantic_analyzer)
        first.analyze(self.tree, self.xpath, self.id)

        # Initialize module symbol table, which was populated by the
        # semantic analyzer.
        # TODO: Why can't FirstPass .analyze() do this?
        self.tree.names = manager.semantic_analyzer.globals

        # Compute (direct) dependencies.
        # Add all direct imports (this is why we needed the first pass).
        # Also keep track of each dependency's source line.
        dependencies = []
        suppressed = []
        dep_line_map = {}  # type: Dict[str, int]  # id -> line
        for id, line in manager.all_imported_modules_in_file(self.tree):
            if id == self.id:
                continue
            # Omit missing modules, as otherwise we could not type-check
            # programs with missing modules.
            if id in manager.missing_modules:
                if id not in dep_line_map:
                    suppressed.append(id)
                    dep_line_map[id] = line
                continue
            if id == '':
                # Must be from a relative import.
                manager.errors.set_file(self.xpath)
                manager.errors.report(line, "No parent module -- cannot perform relative import",
                                      blocker=True)
                continue
            if id not in dep_line_map:
                dependencies.append(id)
                dep_line_map[id] = line
        # Every module implicitly depends on builtins.
        if self.id != 'builtins' and 'builtins' not in dep_line_map:
            dependencies.append('builtins')

        # If self.dependencies is already set, it was read from the
        # cache, but for some reason we're re-parsing the file.
        # NOTE: What to do about race conditions (like editing the
        # file while mypy runs)?  A previous version of this code
        # explicitly checked for this, but ran afoul of other reasons
        # for differences (e.g. --silent-imports).
        self.dependencies = dependencies
        self.suppressed = suppressed
        self.dep_line_map = dep_line_map
        self.check_blockers()

    def patch_parent(self) -> None:
        # Include module in the symbol table of the enclosing package.
        if '.' not in self.id:
            return
        manager = self.manager
        modules = manager.modules
        parent, child = self.id.rsplit('.', 1)
        if parent in modules:
            manager.trace("Added %s.%s" % (parent, child))
            modules[parent].names[child] = SymbolTableNode(MODULE_REF, self.tree, parent)
        else:
            manager.log("Hm... couldn't add %s.%s" % (parent, child))

    def semantic_analysis(self) -> None:
        with self.wrap_context():
            self.manager.semantic_analyzer.visit_file(self.tree, self.xpath)

    def semantic_analysis_pass_three(self) -> None:
        with self.wrap_context():
            self.manager.semantic_analyzer_pass3.visit_file(self.tree, self.xpath)
            if DUMP_TYPE_STATS in self.manager.flags:
                dump_type_stats(self.tree, self.xpath)

    def type_check(self) -> None:
        manager = self.manager
        if manager.target < TYPE_CHECK:
            return
        with self.wrap_context():
            manager.type_checker.visit_file(self.tree, self.xpath)
            if DUMP_INFER_STATS in manager.flags:
                dump_type_stats(self.tree, self.xpath, inferred=True,
                                typemap=manager.type_checker.type_map)
            manager.report_file(self.tree)

    def write_cache(self) -> None:
        if self.path and INCREMENTAL in self.manager.flags and not self.manager.errors.is_errors():
            write_cache(self.id, self.path, self.tree,
                        list(self.dependencies), list(self.suppressed),
                        self.manager)


Graph = Dict[str, State]


def dispatch(sources: List[BuildSource], manager: BuildManager) -> None:
    manager.log("Using new dependency manager")
    graph = load_graph(sources, manager)
    manager.log("Loaded graph with %d nodes" % len(graph))
    process_graph(graph, manager)


def load_graph(sources: List[BuildSource], manager: BuildManager) -> Graph:
    """Given some source files, load the full dependency graph."""
    graph = {}  # type: Graph
    # The deque is used to implement breadth-first traversal.
    # TODO: Consider whether to go depth-first instead.  This may
    # affect the order in which we process files within import cycles.
    new = collections.deque()  # type: collections.deque[State]
    # Seed the graph with the initial root sources.
    for bs in sources:
        try:
            st = State(id=bs.module, path=bs.path, source=bs.text, manager=manager)
        except ModuleNotFound:
            continue
        if st.id in graph:
            manager.errors.set_file(st.xpath)
            manager.errors.report(1, "Duplicate module named '%s'" % st.id)
            manager.errors.raise_error()
        graph[st.id] = st
        new.append(st)
    # Collect dependencies.  We go breadth-first.
    while new:
        st = new.popleft()
        for dep in st.ancestors + st.dependencies:
            if dep not in graph:
                try:
                    if dep in st.ancestors:
                        # TODO: Why not 'if dep not in st.dependencies' ?
                        # Ancestors don't have import context.
                        newst = State(id=dep, path=None, source=None, manager=manager,
                                      ancestor_for=st)
                    else:
                        newst = State(id=dep, path=None, source=None, manager=manager,
                                      caller_state=st, caller_line=st.dep_line_map.get(dep, 1))
                except ModuleNotFound:
                    if dep in st.dependencies:
                        st.dependencies.remove(dep)
                        st.suppressed.append(dep)
                else:
                    assert newst.id not in graph, newst.id
                    graph[newst.id] = newst
                    new.append(newst)
    return graph


def process_graph(graph: Graph, manager: BuildManager) -> None:
    """Process everything in dependency order."""
    sccs = sorted_components(graph)
    manager.log("Found %d SCCs; largest has %d nodes" %
                (len(sccs), max(len(scc) for scc in sccs)))
    # We're processing SCCs from leaves (those without further
    # dependencies) to roots (those from which everything else can be
    # reached).
    for ascc in sccs:
        # Sort the SCC's nodes in *reverse* order or encounter.
        # This is a heuristic for handling import cycles.
        # Note that ascc is a set, and scc is a list.
        scc = sorted(ascc, key=lambda id: -graph[id].order)
        # If builtins is in the list, move it last.  (This is a bit of
        # a hack, but it's necessary because the builtins module is
        # part of a small cycle involving at least {builtins, abc,
        # typing}.  Of these, builtins must be processed last or else
        # some builtin objects will be incompletely processed.)
        if 'builtins' in ascc:
            scc.remove('builtins')
            scc.append('builtins')
        # Because the SCCs are presented in topological sort order, we
        # don't need to look at dependencies recursively for staleness
        # -- the immediate dependencies are sufficient.
        stale_scc = {id for id in scc if not graph[id].is_fresh()}
        fresh = not stale_scc
        deps = set()
        for id in scc:
            deps.update(graph[id].dependencies)
        deps -= ascc
        stale_deps = {id for id in deps if not graph[id].is_fresh()}
        fresh = fresh and not stale_deps
        undeps = set()
        if fresh:
            # Check if any dependencies that were suppressed according
            # to the cache have heen added back in this run.
            # NOTE: Newly suppressed dependencies are handled by is_fresh().
            for id in scc:
                undeps.update(graph[id].suppressed)
            undeps &= graph.keys()
            if undeps:
                fresh = False
        if fresh:
            # All cache files are fresh.  Check that no dependency's
            # cache file is newer than any scc node's cache file.
            oldest_in_scc = min(graph[id].meta.data_mtime for id in scc)
            newest_in_deps = 0 if not deps else max(graph[dep].meta.data_mtime for dep in deps)
            if manager.flags.count(VERBOSE) >= 2:  # Dump all mtimes for extreme debugging.
                all_ids = sorted(ascc | deps, key=lambda id: graph[id].meta.data_mtime)
                for id in all_ids:
                    if id in scc:
                        if graph[id].meta.data_mtime < newest_in_deps:
                            key = "*id:"
                        else:
                            key = "id:"
                    else:
                        if graph[id].meta.data_mtime > oldest_in_scc:
                            key = "+dep:"
                        else:
                            key = "dep:"
                    manager.trace(" %5s %.0f %s" % (key, graph[id].meta.data_mtime, id))
            # If equal, give the benefit of the doubt, due to 1-sec time granularity
            # (on some platforms).
            if oldest_in_scc < newest_in_deps:
                fresh = False
                fresh_msg = "out of date by %.0f seconds" % (newest_in_deps - oldest_in_scc)
            else:
                fresh_msg = "fresh"
        elif undeps:
            fresh_msg = "stale due to changed suppression (%s)" % " ".join(sorted(undeps))
        elif stale_scc:
            fresh_msg = "inherently stale (%s)" % " ".join(sorted(stale_scc))
            if stale_deps:
                fresh_msg += " with stale deps (%s)" % " ".join(sorted(stale_deps))
        else:
            fresh_msg = "stale due to deps (%s)" % " ".join(sorted(stale_deps))
        if len(scc) == 1:
            manager.log("Processing SCC sigleton (%s) as %s" % (" ".join(scc), fresh_msg))
        else:
            manager.log("Processing SCC of size %d (%s) as %s" %
                        (len(scc), " ".join(scc), fresh_msg))
        if fresh:
            process_fresh_scc(graph, scc)
        else:
            process_stale_scc(graph, scc)


def process_fresh_scc(graph: Graph, scc: List[str]) -> None:
    """Process the modules in one SCC from their cached data."""
    for id in scc:
        graph[id].load_tree()
    for id in scc:
        graph[id].patch_parent()
    for id in scc:
        graph[id].fix_cross_refs()
    for id in scc:
        graph[id].calculate_mros()


def process_stale_scc(graph: Graph, scc: List[str]) -> None:
    """Process the modules in one SCC from source code."""
    for id in scc:
        graph[id].mark_stale()
    for id in scc:
        # We may already have parsed the module, or not.
        # If the former, parse_file() is a no-op.
        graph[id].parse_file()
    for id in scc:
        graph[id].patch_parent()
    for id in scc:
        graph[id].semantic_analysis()
    for id in scc:
        graph[id].semantic_analysis_pass_three()
    for id in scc:
        graph[id].type_check()
        graph[id].write_cache()


def sorted_components(graph: Graph) -> List[AbstractSet[str]]:
    """Return the graph's SCCs, topologically sorted by dependencies.

    The sort order is from leaves (nodes without dependencies) to
    roots (nodes on which no other nodes depend).

    This works for a subset of the full dependency graph too;
    dependencies that aren't present in graph.keys() are ignored.
    """
    # Compute SCCs.
    vertices = set(graph)
    edges = {id: [dep for dep in st.dependencies if dep in graph]
             for id, st in graph.items()}
    sccs = list(strongly_connected_components(vertices, edges))
    # Topsort.
    sccsmap = {id: frozenset(scc) for scc in sccs for id in scc}
    data = {}  # type: Dict[AbstractSet[str], Set[AbstractSet[str]]]
    for scc in sccs:
        deps = set()  # type: Set[AbstractSet[str]]
        for id in scc:
            deps.update(sccsmap[x] for x in graph[id].dependencies if x in graph)
        data[frozenset(scc)] = deps
    res = []
    for ready in topsort(data):
        # Sort the sets in ready by reversed smallest State.order.  Examples:
        #
        # - If ready is [{x}, {y}], x.order == 1, y.order == 2, we get
        #   [{y}, {x}].
        #
        # - If ready is [{a, b}, {c, d}], a.order == 1, b.order == 3,
        #   c.order == 2, d.order == 4, the sort keys become [1, 2]
        #   and the result is [{c, d}, {a, b}].
        res.extend(sorted(ready,
                          key=lambda scc: -min(graph[id].order for id in scc)))
    return res


def strongly_connected_components(vertices: Set[str],
                                  edges: Dict[str, List[str]]) -> Iterator[Set[str]]:
    """Compute Strongly Connected Components of a directed graph.

    Args:
      vertices: the labels for the vertices
      edges: for each vertex, gives the target vertices of its outgoing edges

    Returns:
      An iterator yielding strongly connected components, each
      represented as a set of vertices.  Each input vertex will occur
      exactly once; vertices not part of a SCC are returned as
      singleton sets.

    From http://code.activestate.com/recipes/578507/.
    """
    identified = set()  # type: Set[str]
    stack = []  # type: List[str]
    index = {}  # type: Dict[str, int]
    boundaries = []  # type: List[int]

    def dfs(v: str) -> Iterator[Set[str]]:
        index[v] = len(stack)
        stack.append(v)
        boundaries.append(index[v])

        for w in edges[v]:
            if w not in index:
                # For Python >= 3.3, replace with "yield from dfs(w)"
                for scc in dfs(w):
                    yield scc
            elif w not in identified:
                while index[w] < boundaries[-1]:
                    boundaries.pop()

        if boundaries[-1] == index[v]:
            boundaries.pop()
            scc = set(stack[index[v]:])
            del stack[index[v]:]
            identified.update(scc)
            yield scc

    for v in vertices:
        if v not in index:
            # For Python >= 3.3, replace with "yield from dfs(v)"
            for scc in dfs(v):
                yield scc


def topsort(data: Dict[AbstractSet[str],
                       Set[AbstractSet[str]]]) -> Iterable[Set[AbstractSet[str]]]:
    """Topological sort.

    Args:
      data: A map from SCCs (represented as frozen sets of strings) to
            sets of SCCs, its dependencies.  NOTE: This data structure
            is modified in place -- for normalization purposes,
            self-dependencies are removed and entries representing
            orphans are added.

    Returns:
      An iterator yielding sets of SCCs that have an equivalent
      ordering.  NOTE: The algorithm doesn't care about the internal
      structure of SCCs.

    Example:
      Suppose the input has the following structure:

        {A: {B, C}, B: {D}, C: {D}}

      This is normalized to:

        {A: {B, C}, B: {D}, C: {D}, D: {}}

      The algorithm will yield the following values:

        {D}
        {B, C}
        {A}

    From http://code.activestate.com/recipes/577413/.
    """
    # TODO: Use a faster algorithm?
    for k, v in data.items():
        v.discard(k)  # Ignore self dependencies.
    for item in set.union(*data.values()) - set(data.keys()):
        data[item] = set()
    while True:
        ready = {item for item, dep in data.items() if not dep}
        if not ready:
            break
        yield ready
        data = {item: (dep - ready)
                for item, dep in data.items()
                if item not in ready}
    assert not data, "A cyclic dependency exists amongst %r" % data
