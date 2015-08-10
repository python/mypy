"""Facilities to build mypy programs and modules they depend on.

Parse, analyze and translate the source files of a program in the correct
order (based on file dependencies), and collect the results.

This module only directs a build, which is performed in multiple passes per
file.  The individual passes are implemented in separate modules.

The function build() is the main interface to this module.
"""

import os
import os.path
import shlex
import subprocess
import sys
from os.path import dirname, basename

from typing import Dict, List, Tuple, cast, Set, Union

from mypy.types import Type
from mypy.nodes import MypyFile, Node, Import, ImportFrom, ImportAll
from mypy.nodes import SymbolTableNode, MODULE_REF
from mypy.semanal import SemanticAnalyzer, FirstPass, ThirdPass
from mypy.checker import TypeChecker
from mypy.errors import Errors, CompileError
from mypy import parse
from mypy import stats


debug = False


# Build targets (for selecting compiler passes)
SEMANTIC_ANALYSIS = 0   # Semantic analysis only
TYPE_CHECK = 1          # Type check


# Build flags
DO_NOT_RUN = 'do-not-run'        # Only type check, don't run the program
VERBOSE = 'verbose'              # More verbose messages (for troubleshooting)
MODULE = 'module'                # Build/run module as a script
TEST_BUILTINS = 'test-builtins'  # Use stub builtins to speed up tests

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


def build(program_path: str,
          target: int,
          module: str = None,
          program_text: Union[str, bytes] = None,
          alt_lib_path: str = None,
          bin_dir: str = None,
          output_dir: str = None,
          pyversion: int = 3,
          custom_typing_module: str = None,
          html_report_dir: str = None,
          flags: List[str] = None,
          python_path: bool = False) -> BuildResult:
    """Build a mypy program.

    A single call to build performs parsing, semantic analysis and optionally
    type checking and other build passes for the program *and* all imported
    modules, recursively.

    Return BuildResult if successful; otherwise raise CompileError.

    Arguments:
      program_path: the path to the main source file (if module argument is
        given, this can be None => will be looked up)
      target: select passes to perform (a build target constant, e.g. C)
    Optional arguments:
      module: name of the initial module; __main__ by default
      program_text: the main source file contents; if omitted, read from file
      alt_lib_dir: an additional directory for looking up library modules
        (takes precedence over other directories)
      bin_dir: directory containing the mypy script, used for finding data
        directories; if omitted, use '.' as the data directory
      output_dir: directory where the output (Python) is stored
      pyversion: Python version (2 for 2.x or 3 for 3.x)
      custom_typing_module: if not None, use this module id as an alias for typing
      flags: list of build options (e.g. COMPILE_ONLY)
    """
    flags = flags or []
    module = module or '__main__'

    data_dir = default_data_dir(bin_dir)

    # Determine the default module search path.
    lib_path = default_lib_path(data_dir, target, pyversion, python_path)

    if TEST_BUILTINS in flags:
        # Use stub builtins (to speed up test cases and to make them easier to
        # debug).
        lib_path.insert(0, os.path.join('mypy', 'test', 'data', 'lib-stub'))
    elif program_path:
        # Include directory of the program file in the module search path.
        lib_path.insert(
            0, remove_cwd_prefix_from_path(dirname(program_path)))
    else:
        # Building/running a module.
        lib_path.insert(0, os.getcwd())

    # If provided, insert the caller-supplied extra module path to the
    # beginning (highest priority) of the search path.
    if alt_lib_path:
        lib_path.insert(0, alt_lib_path)

    # Construct a build manager object that performs all the stages of the
    # build in the correct order.
    #
    # Ignore current directory prefix in error messages.
    manager = BuildManager(data_dir, lib_path, target, output_dir,
                           pyversion=pyversion, flags=flags,
                           ignore_prefix=os.getcwd(),
                           custom_typing_module=custom_typing_module,
                           html_report_dir=html_report_dir)

    program_path = program_path or lookup_program(module, lib_path)
    if program_text is None:
        program_text = read_program(program_path)

    # Construct information that describes the initial file. __main__ is the
    # implicit module id and the import context is empty initially ([]).
    info = StateInfo(program_path, module, [], manager)
    # Perform the build by sending the file as new file (UnprocessedFile is the
    # initial state of all files) to the manager. The manager will process the
    # file and all dependant modules recursively.
    result = manager.process(UnprocessedFile(info, program_text))
    if 'html-report' in flags:
        stats.generate_html_index(html_report_dir)
    return result


def default_data_dir(bin_dir: str) -> str:
    if not bin_dir:
        # Default to current directory.
        return ''
    base = os.path.basename(bin_dir)
    dir = os.path.dirname(bin_dir)
    if (sys.platform == 'win32' and base.lower() == 'scripts'
            and not os.path.isdir(os.path.join(dir, 'stubs'))):
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


def default_lib_path(data_dir: str, target: int, pyversion: int,
        python_path: bool) -> List[str]:
    """Return default standard library search paths."""
    # IDEA: Make this more portable.
    path = []  # type: List[str]

    # Add MYPYPATH environment variable to library path, if defined.
    path_env = os.getenv('MYPYPATH')
    if path_env is not None:
        path[:0] = path_env.split(os.pathsep)

    # Add library stubs directory. By convention, they are stored in the
    # stubs/x.y directory of the mypy installation.
    version_dir = '3.2'
    if pyversion < 3:
        version_dir = '2.7'
    path.append(os.path.join(data_dir, 'stubs', version_dir))
    path.append(os.path.join(data_dir, 'stubs-auto', version_dir))
    # Add py3.3 and 3.4 stubs.
    if sys.version_info.major == 3:
        versions = ['3.' + str(x) for x in range(3, sys.version_info.minor + 1)]
        for v in versions:
            path.append(os.path.join(data_dir, 'stubs', v))

    # Add fallback path that can be used if we have a broken installation.
    if sys.platform != 'win32':
        path.append('/usr/local/lib/mypy')

    # Contents of Python's sys.path go last, to prefer the stubs
    if python_path:
        path.extend(sys.path)

    return path


def lookup_program(module: str, lib_path: List[str]) -> str:
    # Modules are .py and not .pyi
    path = find_module(module, lib_path)
    if path:
        return path
    else:
        raise CompileError([
            "mypy: can't find module '{}'".format(module)])


def read_program(path: str) -> bytes:
    try:
        with open(path, 'rb') as file:
            text = file.read()
    except IOError as ioerr:
        raise CompileError([
            "mypy: can't read file '{}': {}".format(path, ioerr.strerror)])
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
      output_dir:      Store output files here (Python)
      pyversion:       Python version (2 or 3)
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
                 output_dir: str,
                 pyversion: int,
                 flags: List[str],
                 ignore_prefix: str,
                 custom_typing_module: str,
                 html_report_dir: str) -> None:
        self.data_dir = data_dir
        self.errors = Errors()
        self.errors.set_ignore_prefix(ignore_prefix)
        self.lib_path = lib_path
        self.target = target
        self.output_dir = output_dir
        self.pyversion = pyversion
        self.flags = flags
        self.custom_typing_module = custom_typing_module
        self.html_report_dir = html_report_dir
        self.semantic_analyzer = SemanticAnalyzer(lib_path, self.errors,
                                                  pyversion=pyversion)
        self.semantic_analyzer_pass3 = ThirdPass(self.errors)
        self.type_checker = TypeChecker(self.errors,
                                        self.semantic_analyzer.modules,
                                        self.pyversion)
        self.states = []  # type: List[State]
        self.module_files = {}  # type: Dict[str, str]
        self.module_deps = {}  # type: Dict[Tuple[str, str], bool]
        self.missing_modules = set()  # type: Set[str]

    def process(self, initial_state: 'UnprocessedFile') -> BuildResult:
        """Perform a build.

        The argument is a state that represents the main program
        file. This method should only be called once per a build
        manager object.  The return values are identical to the return
        values of the build function.
        """
        self.states.append(initial_state)

        # Process states in a loop until all files (states) have been
        # semantically analyzed or type checked (depending on target).
        #
        # We type check all files before the rest of the passes so that we can
        # report errors and fail as quickly as possible.
        while True:
            # Find the next state that has all its dependencies met.
            next = self.next_available_state()
            if not next:
                trace('done')
                break

            # Potentially output some debug information.
            trace('next {} ({})'.format(next.path, next.state()))

            # Set the import context for reporting error messages correctly.
            self.errors.set_import_context(next.import_context)
            # Process the state. The process method is reponsible for adding a
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
        raise RuntimeError('%s not found' % str)

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
            if os.path.basename(file.path) == '__init__.py':
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

    def get_python_out_path(self, f: MypyFile) -> str:
        if f.fullname() == '__main__':
            return os.path.join(self.output_dir, basename(f.path))
        else:
            components = f.fullname().split('.')
            if os.path.basename(f.path) == '__init__.py':
                components.append('__init__.py')
            else:
                components[-1] += '.py'
            return os.path.join(self.output_dir, *components)

    def log(self, message: str) -> None:
        if VERBOSE in self.flags:
            print('LOG: %s' % message)


def remove_cwd_prefix_from_path(p: str) -> str:
    """Remove current working directory prefix from p, if present.

    If the result would be empty, return '.' instead.
    """
    cur = os.getcwd()
    # Add separator to the end of the path, unless one is already present.
    if basename(cur) != '':
        cur += os.sep
    # Remove current directory prefix from the path, if present.
    if p.startswith(cur):
        p = p[len(cur):]
    # Avoid returning an empty path; replace that with '.'.
    if p == '':
        p = '.'
    return p


def is_stub(path: str) -> bool:
    """Does path refer to a stubs file?

    Currently check if there is a 'stubs' directory component somewhere
    in the path.
    """
    # TODO more precise check
    dirname, basename = os.path.split(path)
    if basename == '':
        return False
    else:
        stubnames = ['stubs', 'stubs-auto']
        return (basename in stubnames) or is_stub(dirname)


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


class UnprocessedFile(State):
    def __init__(self, info: StateInfo, program_text: Union[str, bytes]) -> None:
        super().__init__(info)
        self.program_text = program_text
        trace('waiting {}'.format(info.path))

        # Add surrounding package(s) as dependencies.
        for p in super_packages(self.id):
            if not self.import_module(p):
                # Could not find a module. Typically the reason is a misspelled
                # module name, or the module has not been installed.
                self.fail(self.path, 1, "No module named '{}'".format(p))
            self.dependencies.append(p)

    def process(self) -> None:
        """Parse the file, store global names and advance to the next state."""
        tree = self.parse(self.program_text, self.path)

        # Store the parsed module in the shared module symbol table.
        self.manager.semantic_analyzer.modules[self.id] = tree

        if '.' in self.id:
            # Include module in the symbol table of the enclosing package.
            c = self.id.split('.')
            p = '.'.join(c[:-1])
            sem_anal = self.manager.semantic_analyzer
            sem_anal.modules[p].names[c[-1]] = SymbolTableNode(
                MODULE_REF, tree, p)

        if self.id != 'builtins':
            # The builtins module is imported implicitly in every program (it
            # contains definitions of int, print etc.).
            trace('import builtins')
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
                    self.fail(self.path, line, "No module named '{}'".format(id), blocker=False)
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
            # Do nothing:f already being compiled.
            return True

        path, text = read_module_source_from_file(id, self.manager.lib_path)
        if text is not None:
            info = StateInfo(path, id, self.errors().import_context(),
                             self.manager)
            self.manager.states.append(UnprocessedFile(info, text))
            self.manager.module_files[id] = path
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
                           custom_typing_module=self.manager.custom_typing_module)
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
            trace('{} dependencies: {}'.format(info.path, imp))

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
        if 'dump-type-stats' in self.manager.flags:
            stats.dump_type_stats(self.tree, self.tree.path)
        self.switch_state(SemanticallyAnalyzedFile(self.info(), self.tree))

    def state(self) -> int:
        return PARTIAL_SEMANTIC_ANALYSIS_STATE


class SemanticallyAnalyzedFile(ParsedFile):
    def process(self) -> None:
        """Type check file and advance to the next state."""
        if self.manager.target >= TYPE_CHECK:
            self.type_checker().visit_file(self.tree, self.tree.path)
            if 'dump-infer-stats' in self.manager.flags:
                stats.dump_type_stats(self.tree, self.tree.path, inferred=True,
                                      typemap=self.manager.type_checker.type_map)
            elif 'html-report' in self.manager.flags:
                stats.generate_html_report(
                    self.tree, self.tree.path,
                    type_map=self.manager.type_checker.type_map,
                    output_dir=self.manager.html_report_dir)

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


def trace(s):
    if debug:
        print(s)


def read_module_source_from_file(id: str,
                                 lib_path: List[str]) -> Tuple[str, str]:
    """Find and read the source file of a module.

    Return a pair (path, file contents). Return (None, None) if the module
    could not be found or read.

    Arguments:
      id:       module name, a string of form 'foo' or 'foo.bar'
      lib_path: library search path
    """
    path = find_module(id, lib_path)
    if path is not None:
        text = ''
        try:
            f = open(path)
            try:
                text = f.read()
            finally:
                f.close()
        except IOError:
            return None, None
        return path, text
    else:
        return None, None


def find_module(id: str, lib_path: List[str]) -> str:
    """Return the path of the module source file, or None if not found."""
    for pathitem in lib_path:
        for extension in PYTHON_EXTENSIONS:
            comp = id.split('.')
            path = os.path.join(pathitem, os.sep.join(comp[:-1]), comp[-1] + extension)
            if not os.path.isfile(path):
                path = os.path.join(pathitem, os.sep.join(comp), '__init__{}'.format(extension))
            if os.path.isfile(path) and verify_module(id, path):
                return path
    return None


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
