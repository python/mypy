"""Facilities to analyze entire programs, including imported modules.

Parse and analyze the source files of a program in the correct order
(based on file dependencies), and collect the results.

This module only directs a build, which is performed in multiple passes per
file.  The individual passes are implemented in separate modules.

The function build() is the main interface to this module.
"""

import os
import os.path
import shlex
import subprocess
import sys
import re
from os.path import dirname, basename

from typing import Dict, List, Tuple, Iterable, cast, Set, Union, Optional

from mypy.types import Type
from mypy.nodes import MypyFile, Node, Import, ImportFrom, ImportAll
from mypy.nodes import SymbolTableNode, MODULE_REF
from mypy.semanal import SemanticAnalyzer, FirstPass, ThirdPass
from mypy.checker import TypeChecker
from mypy.errors import Errors, CompileError
from mypy import parse
from mypy import stats
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

# State ids. These describe the states a source file / module can be in a
# build.

# We aren't processing this source file yet (no associated state object).
UNSEEN_STATE = 0
# The source file has a state object, but we haven't done anything with it yet.
UNPROCESSED_STATE = 1
# We've parsed the source file.
PARSED_STATE = 2
# We've done the first two passes of semantic analysis.
PARTIAL_SEMANTIC_ANALYSIS_STATE = 3
# We've semantically analyzed the source file.
SEMANTICALLY_ANALYSED_STATE = 4
# We've type checked the source file (and all its dependencies).
TYPE_CHECKED_STATE = 5

PYTHON_EXTENSIONS = ['.pyi', '.py']

final_state = TYPE_CHECKED_STATE


def earlier_state(s: int, t: int) -> bool:
    return s < t


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

    def load(self, lib_path, pyversion: Tuple[int, int]) -> str:
        """Load the module if needed. This also has the side effect
        of calculating the effective path for modules."""
        if self.text is not None:
            return self.text

        self.path = self.path or lookup_program(self.module, lib_path)
        return read_program(self.path, pyversion)

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

    # TODO Reports is global to a build manager but only supports a single "main file"
    # Fix this.
    reports = Reports(sources[0].effective_path, data_dir, report_dirs)

    # Construct a build manager object that performs all the stages of the
    # build in the correct order.
    #
    # Ignore current directory prefix in error messages.
    manager = BuildManager(data_dir, lib_path, target,
                           pyversion=pyversion, flags=flags,
                           ignore_prefix=os.getcwd(),
                           custom_typing_module=custom_typing_module,
                           implicit_any=implicit_any,
                           reports=reports)

    # Construct information that describes the initial files. __main__ is the
    # implicit module id and the import context is empty initially ([]).
    initial_states = []  # type: List[UnprocessedFile]
    for source in sources:
        content = source.load(lib_path, pyversion)
        info = StateInfo(source.effective_path, source.module, [], manager)
        initial_state = UnprocessedFile(info, content)
        initial_states += [initial_state]

    # Perform the build by sending the files as new file (UnprocessedFile is the
    # initial state of all files) to the manager. The manager will process the
    # file and all dependant modules recursively.
    result = manager.process(initial_states)
    reports.finish()
    return result


def default_data_dir(bin_dir: str) -> str:
    # TODO fix this logic
    if not bin_dir:
        mypy_package = os.path.dirname(__file__)
        parent = os.path.dirname(mypy_package)
        if os.path.basename(parent) == 'site-packages':
            # Installed in site-packages, but invoked with python3 -m mypy;
            # __file__ is .../blah/lib/python3.N/site-packages/mypy/__init__.py;
            # blah may be a virtualenv or /usr/local.  We want .../blah/lib/mypy.
            lib = os.path.dirname(os.path.dirname(parent))
            if os.path.basename(lib) == 'lib':
                return os.path.join(lib, 'mypy')
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
        return os.path.dirname(bin_dir)
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


def lookup_program(module: str, lib_path: List[str]) -> str:
    # Modules are .py or .pyi
    path = find_module(module, lib_path)
    if path:
        return path
    else:
        raise CompileError([
            "mypy: can't find module '{}'".format(module)])


def read_program(path: str, pyversion: Tuple[int, int]) -> str:
    try:
        text = read_with_python_encoding(path, pyversion)
    except IOError as ioerr:
        raise CompileError([
            "mypy: can't read file '{}': {}".format(path, ioerr.strerror)])
    except UnicodeDecodeError as decodeerr:
        raise CompileError([
            "mypy: can't decode file '{}': {}".format(path, str(decodeerr))])
    return text


class BuildManager:
    """This is the central class for building a mypy program.

    It coordinates parsing, import processing, semantic analysis and
    type checking. It manages state objects that actually perform the
    build steps.

    Attributes:
      data_dir:        Mypy data directory (contains stubs)
      target:          Build target; selects which passes to perform
      lib_path:        Library path for looking up modules
      semantic_analyzer:
                       Semantic analyzer, pass 2
      semantic_analyzer_pass3:
                       Semantic analyzer, pass 3
      type_checker:    Type checker
      errors:          Used for reporting all errors
      pyversion:       Python version (major, minor)
      flags:           Build options
      states:          States of all individual files that are being
                       processed. Each file in a build is always represented
                       by a single state object (after it has been encountered
                       for the first time). This is the only place where
                       states are stored.
      module_files:    Map from module name to source file path. There is a
                       1:1 mapping between modules and source files.
      module_deps:     Cache for module dependencies (direct or indirect).
                       Item (m, n) indicates whether m depends on n (directly
                       or indirectly).
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
        modules = self.semantic_analyzer.modules
        self.semantic_analyzer_pass3 = ThirdPass(modules, self.errors)
        self.type_checker = TypeChecker(self.errors,
                                        modules,
                                        self.pyversion,
                                        DISALLOW_UNTYPED_CALLS in self.flags)
        self.states = []  # type: List[State]
        self.module_files = {}  # type: Dict[str, str]
        self.module_deps = {}  # type: Dict[Tuple[str, str], bool]
        self.missing_modules = set()  # type: Set[str]

    def process(self, initial_states: List['UnprocessedFile']) -> BuildResult:
        """Perform a build.

        The argument is a state that represents the main program
        file. This method should only be called once per a build
        manager object.  The return values are identical to the return
        values of the build function.
        """
        self.states += initial_states
        for initial_state in initial_states:
            self.module_files[initial_state.id] = initial_state.path
        for initial_state in initial_states:
            initial_state.load_dependencies()

        # Process states in a loop until all files (states) have been
        # semantically analyzed or type checked (depending on target).
        #
        # We type check all files before the rest of the passes so that we can
        # report errors and fail as quickly as possible.
        while True:
            # Find the next state that has all its dependencies met.
            next = self.next_available_state()
            if not next:
                self.trace('done')
                break

            # Potentially output some debug information.
            self.trace('next {} ({})'.format(next.path, next.state()))

            # Set the import context for reporting error messages correctly.
            self.errors.set_import_context(next.import_context)
            # Process the state. The process method is responsible for adding a
            # new state object representing the new state of the file.
            next.process()

            # Raise exception if the build failed. The build can fail for
            # various reasons, such as parse error, semantic analysis error,
            # etc.
            if self.errors.is_blockers():
                self.errors.raise_error()

        # If there were no errors, all files should have been fully processed.
        for s in self.states:
            assert s.state() == final_state, (
                '{} still unprocessed in state {}'.format(s.path, s.state()))

        if self.errors.is_errors():
            self.errors.raise_error()

        # Collect a list of all files.
        trees = []  # type: List[MypyFile]
        for state in self.states:
            trees.append(cast(ParsedFile, state).tree)

        # Perform any additional passes after type checking for all the files.
        self.final_passes(trees, self.type_checker.type_map)

        return BuildResult(self.semantic_analyzer.modules,
                           self.type_checker.type_map)

    def next_available_state(self) -> 'State':
        """Find a ready state (one that has all its dependencies met)."""
        i = len(self.states) - 1
        while i >= 0:
            if self.states[i].is_ready():
                num_incomplete = self.states[i].num_incomplete_deps()
                if num_incomplete == 0:
                    # This is perfect; no need to look for the best match.
                    return self.states[i]
            i -= 1
        return None

    def has_module(self, name: str) -> bool:
        """Have we seen a module yet?"""
        return name in self.module_files

    def file_state(self, path: str) -> int:
        """Return the state of a source file.

        In particular, return UNSEEN_STATE if the file has no associated
        state.

        This function does not consider any dependencies.
        """
        for s in self.states:
            if s.path == path:
                return s.state()
        return UNSEEN_STATE

    def module_state(self, name: str) -> int:
        """Return the state of a module.

        In particular, return UNSEEN_STATE if the file has no associated
        state.

        This considers also module dependencies.
        """
        if not self.has_module(name):
            return UNSEEN_STATE
        state = final_state
        fs = self.file_state(self.module_files[name])
        if earlier_state(fs, state):
            state = fs
        return state

    def is_dep(self, m1: str, m2: str, done: Set[str] = None) -> bool:
        """Does m1 import m2 directly or indirectly?"""
        # Have we computed this previously?
        dep = self.module_deps.get((m1, m2))
        if dep is not None:
            return dep

        if not done:
            done = set([m1])

        # m1 depends on m2 iff one of the deps of m1 depends on m2.
        st = self.lookup_state(m1)
        for m in st.dependencies:
            if m in done:
                continue
            done.add(m)
            # Cache this dependency.
            self.module_deps[m1, m] = True
            # Search recursively.
            if m == m2 or self.is_dep(m, m2, done):
                # Yes! Mark it in the cache.
                self.module_deps[m1, m2] = True
                return True
        # No dependency. Mark it in the cache.
        self.module_deps[m1, m2] = False
        return False

    def lookup_state(self, module: str) -> 'State':
        for state in self.states:
            if state.id == module:
                return state
        raise RuntimeError('%s not found' % module)

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

    def final_passes(self, files: List[MypyFile],
                     types: Dict[Node, Type]) -> None:
        """Perform the code generation passes for type checked files."""
        if self.target in [SEMANTIC_ANALYSIS, TYPE_CHECK]:
            pass  # Nothing to do.
        else:
            raise RuntimeError('Unsupported target %d' % self.target)

    def log(self, message: str) -> None:
        if VERBOSE in self.flags:
            print('LOG:', message, file=sys.stderr)

    def trace(self, message: str) -> None:
        if self.flags.count(VERBOSE) >= 2:
            print('TRACE:', message, file=sys.stderr)


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


class StateInfo:
    """Description of a source file that is being built."""

    def __init__(self, path: str, id: str,
                 import_context: List[Tuple[str, int]],
                 manager: BuildManager) -> None:
        """Initialize state information.

        Arguments:
          path:    Path to the file
          id:      Module id, such as 'os.path' or '__main__' (for the main
                   program file)
          import_context:
                   The import trail that caused this module to be
                   imported (path, line) tuples
          manager: The manager that manages this build
        """
        self.path = path
        self.id = id
        self.import_context = import_context
        self.manager = manager


class State:
    """Abstract base class for build states.

    There is always at most one state per source file.
    """

    # The StateInfo attributes are duplicated here for convenience.
    path = ''
    id = ''
    import_context = None  # type: List[Tuple[str, int]]
    manager = None  # type: BuildManager
    # Modules that this file directly depends on (in no particular order).
    dependencies = None  # type: List[str]

    def __init__(self, info: StateInfo) -> None:
        self.path = info.path
        self.id = info.id
        self.import_context = info.import_context
        self.manager = info.manager
        self.dependencies = []

    def info(self) -> StateInfo:
        return StateInfo(self.path, self.id, self.import_context, self.manager)

    def process(self) -> None:
        raise RuntimeError('Not implemented')

    def is_ready(self) -> bool:
        """Return True if all dependencies are at least in the same state
        as this object (but not in the initial state).
        """
        for module in self.dependencies:
            state = self.manager.module_state(module)
            if earlier_state(state,
                             self.state()) or state == UNPROCESSED_STATE:
                return False
        return True

    def num_incomplete_deps(self) -> int:
        """Return the number of dependencies that are ready but incomplete."""
        return 0  # Does not matter in this state

    def state(self) -> int:
        raise RuntimeError('Not implemented')

    def switch_state(self, state_object: 'State') -> None:
        """Called by state objects to replace the state of the file.

        Also notify the manager.
        """
        for i in range(len(self.manager.states)):
            if self.manager.states[i].path == state_object.path:
                self.manager.states[i] = state_object
                return
        raise RuntimeError('State for {} not found'.format(state_object.path))

    def errors(self) -> Errors:
        return self.manager.errors

    def semantic_analyzer(self) -> SemanticAnalyzer:
        return self.manager.semantic_analyzer

    def semantic_analyzer_pass3(self) -> ThirdPass:
        return self.manager.semantic_analyzer_pass3

    def type_checker(self) -> TypeChecker:
        return self.manager.type_checker

    def fail(self, path: str, line: int, msg: str, blocker: bool = True) -> None:
        """Report an error in the build (e.g. if could not find a module)."""
        self.errors().set_file(path)
        self.errors().report(line, msg, blocker=blocker)

    def module_not_found(self, path: str, line: int, id: str) -> None:
        self.errors().set_file(path)
        stub_msg = "(Stub files are from https://github.com/python/typeshed)"
        if ((self.manager.pyversion[0] == 2 and moduleinfo.is_py2_std_lib_module(id)) or
                (self.manager.pyversion[0] >= 3 and moduleinfo.is_py3_std_lib_module(id))):
            self.errors().report(
                line, "No library stub file for standard library module '{}'".format(id))
            self.errors().report(line, stub_msg, severity='note', only_once=True)
        elif moduleinfo.is_third_party_module(id):
            self.errors().report(line, "No library stub file for module '{}'".format(id))
            self.errors().report(line, stub_msg, severity='note', only_once=True)
        else:
            self.errors().report(line, "Cannot find module named '{}'".format(id))
            self.errors().report(line, "(Perhaps setting MYPYPATH would help)", severity='note',
                                 only_once=True)


class UnprocessedFile(State):
    def __init__(self, info: StateInfo, program_text: str) -> None:
        super().__init__(info)
        self.program_text = program_text
        self.silent = SILENT_IMPORTS in self.manager.flags

    def load_dependencies(self):
        # Add surrounding package(s) as dependencies.
        for p in super_packages(self.id):
            if p in self.manager.missing_modules:
                continue
            if not self.import_module(p):
                # Could not find a module. Typically the reason is a
                # misspelled module name, missing stub, module not in
                # search path or the module has not been installed.
                if self.silent:
                    self.manager.missing_modules.add(p)
                else:
                    self.module_not_found(self.path, 1, p)
            else:
                self.dependencies.append(p)

    def process(self) -> None:
        """Parse the file, store global names and advance to the next state."""
        if self.id in self.manager.semantic_analyzer.modules:
            self.fail(self.path, 1, "Duplicate module named '{}'".format(self.id))
            return

        tree = self.parse(self.program_text, self.path)

        # Store the parsed module in the shared module symbol table.
        self.manager.semantic_analyzer.modules[self.id] = tree

        if '.' in self.id:
            # Include module in the symbol table of the enclosing package.
            c = self.id.split('.')
            p = '.'.join(c[:-1])
            sem_anal = self.manager.semantic_analyzer
            if p in sem_anal.modules:
                sem_anal.modules[p].names[c[-1]] = SymbolTableNode(
                    MODULE_REF, tree, p)

        if self.id != 'builtins':
            # The builtins module is imported implicitly in every program (it
            # contains definitions of int, print etc.).
            self.manager.trace('import builtins')
            if not self.import_module('builtins'):
                self.fail(self.path, 1, 'Could not find builtins')

        # Do the first pass of semantic analysis: add top-level definitions in
        # the file to the symbol table. We must do this before processing imports,
        # since this may mark some import statements as unreachable.
        first = FirstPass(self.semantic_analyzer())
        first.analyze(tree, self.path, self.id)

        # Add all directly imported modules to be processed (however they are
        # not processed yet, just waiting to be processed).
        for id, line in self.manager.all_imported_modules_in_file(tree):
            self.errors().push_import_context(self.path, line)
            try:
                res = self.import_module(id)
            finally:
                self.errors().pop_import_context()
            if not res:
                if id == '':
                    # Must be from a relative import.
                    self.fail(self.path, line,
                              "No parent module -- cannot perform relative import".format(id),
                              blocker=True)
                else:
                    if (line not in tree.ignored_lines and
                            'import' not in tree.weak_opts and
                            not self.silent):
                        self.module_not_found(self.path, line, id)
                self.manager.missing_modules.add(id)

        # Initialize module symbol table, which was populated by the semantic
        # analyzer.
        tree.names = self.semantic_analyzer().globals

        # Replace this state object with a parsed state in BuildManager.
        self.switch_state(ParsedFile(self.info(), tree))

    def import_module(self, id: str) -> bool:
        """Schedule a module to be processed.

        Add an unprocessed state object corresponding to the module to the
        manager, or do nothing if the module already has a state object.
        """
        if self.manager.has_module(id):
            # Do nothing: already being compiled.
            return True

        if id == 'builtins' and self.manager.pyversion[0] == 2:
            # The __builtin__ module is called internally by mypy 'builtins' in Python 2 mode
            # (similar to Python 3), but the stub file is __builtin__.pyi. The reason is that
            # a lot of code hard codes 'builtins.x' and this it's easier to work it around like
            # this. It also means that the implementation can mostly ignore the difference and
            # just assume 'builtins' everywhere, which simplifies code.
            file_id = '__builtin__'
        else:
            file_id = id
        path, text = read_module_source_from_file(file_id, self.manager.lib_path,
                                                  self.manager.pyversion, self.silent)
        if text is not None:
            info = StateInfo(path, id, self.errors().import_context(),
                             self.manager)
            new_file = UnprocessedFile(info, text)
            self.manager.states.append(new_file)
            self.manager.module_files[id] = path
            new_file.load_dependencies()
            return True
        else:
            return False

    def parse(self, source_text: Union[str, bytes], fnam: str) -> MypyFile:
        """Parse the source of a file with the given name.

        Raise CompileError if there is a parse error.
        """
        num_errs = self.errors().num_messages()
        tree = parse.parse(source_text, fnam, self.errors(),
                           pyversion=self.manager.pyversion,
                           custom_typing_module=self.manager.custom_typing_module,
                           implicit_any=self.manager.implicit_any,
                           fast_parser=FAST_PARSER in self.manager.flags)
        tree._fullname = self.id
        if self.errors().num_messages() != num_errs:
            self.errors().raise_error()
        return tree

    def state(self) -> int:
        return UNPROCESSED_STATE


class ParsedFile(State):
    tree = None  # type: MypyFile

    def __init__(self, info: StateInfo, tree: MypyFile) -> None:
        super().__init__(info)
        self.tree = tree

        # Build a list all directly imported moules (dependencies).
        imp = []  # type: List[str]
        for id, line in self.manager.all_imported_modules_in_file(tree):
            # Omit missing modules, as otherwise we could not type check
            # programs with missing modules.
            if id not in self.manager.missing_modules and id != self.id:
                imp.append(id)
        if self.id != 'builtins':
            imp.append('builtins')

        if imp != []:
            self.manager.trace('{} dependencies: {}'.format(info.path, imp))

        # Record the dependencies. Note that the dependencies list also
        # contains any superpackages and we must preserve them (e.g. os for
        # os.path).
        self.dependencies.extend(imp)

    def process(self) -> None:
        """Semantically analyze file and advance to the next state."""
        self.semantic_analyzer().visit_file(self.tree, self.tree.path)
        self.switch_state(PartiallySemanticallyAnalyzedFile(self.info(),
                                                            self.tree))

    def num_incomplete_deps(self) -> int:
        """Return the number of dependencies that are incomplete.

        Here complete means that their state is *later* than this module.
        Cyclic dependencies are omitted to break cycles forcibly (and somewhat
        arbitrarily).
        """
        incomplete = 0
        for module in self.dependencies:
            state = self.manager.module_state(module)
            if (not earlier_state(self.state(), state) and
                    not self.manager.is_dep(module, self.id)):
                incomplete += 1
        return incomplete

    def state(self) -> int:
        return PARSED_STATE


class PartiallySemanticallyAnalyzedFile(ParsedFile):
    def process(self) -> None:
        """Perform final pass of semantic analysis and advance state."""
        self.semantic_analyzer_pass3().visit_file(self.tree, self.tree.path)
        if DUMP_TYPE_STATS in self.manager.flags:
            stats.dump_type_stats(self.tree, self.tree.path)
        self.switch_state(SemanticallyAnalyzedFile(self.info(), self.tree))

    def state(self) -> int:
        return PARTIAL_SEMANTIC_ANALYSIS_STATE


class SemanticallyAnalyzedFile(ParsedFile):
    def process(self) -> None:
        """Type check file and advance to the next state."""
        if self.manager.target >= TYPE_CHECK:
            self.type_checker().visit_file(self.tree, self.tree.path)
            if DUMP_INFER_STATS in self.manager.flags:
                stats.dump_type_stats(self.tree, self.tree.path, inferred=True,
                                      typemap=self.manager.type_checker.type_map)
            self.manager.reports.file(self.tree, type_map=self.manager.type_checker.type_map)

        # FIX remove from active state list to speed up processing

        self.switch_state(TypeCheckedFile(self.info(), self.tree))

    def state(self) -> int:
        return SEMANTICALLY_ANALYSED_STATE


class TypeCheckedFile(SemanticallyAnalyzedFile):
    def process(self) -> None:
        """Finished, so cannot process."""
        raise RuntimeError('Cannot process TypeCheckedFile')

    def is_ready(self) -> bool:
        """Finished, so cannot ever become ready."""
        return False

    def state(self) -> int:
        return TYPE_CHECKED_STATE


def read_module_source_from_file(id: str,
                                 lib_path: Iterable[str],
                                 pyversion: Tuple[int, int],
                                 silent: bool) -> Tuple[Optional[str], Optional[str]]:
    """Find and read the source file of a module.

    Return a pair (path, file contents). Return (None, None) if the module
    could not be found or read.

    Args:
      id:       module name, a string of form 'foo' or 'foo.bar'
      lib_path: library search path
      silent:   if set, don't import .py files (only .pyi files)
    """
    path = find_module(id, lib_path)
    if path is not None:
        if silent and not path.endswith('.pyi'):
            return None, None
        try:
            text = read_with_python_encoding(path, pyversion)
        except IOError:
            return None, None
        return path, text
    else:
        return None, None


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


def super_packages(id: str) -> List[str]:
    """Return the surrounding packages of a module, e.g. ['os'] for os.path."""
    c = id.split('.')
    res = []  # type: List[str]
    for i in range(1, len(c)):
        res.append('.'.join(c[:i]))
    return res


def make_parent_dirs(path: str) -> None:
    parent = os.path.dirname(path)
    try:
        os.makedirs(parent)
    except OSError:
        pass


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
