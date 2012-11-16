import os
import os.path
from mtypes import Typ
from nodes import MypyFile, Node, Import, ImportFrom, ImportAll, MODULE_REF
from nodes import SymbolTableNode
from semanal import TypeInfoMap, SemanticAnal
from os.path import dirname, basename
from sys import platform
from checker import TypeChecker
from errors import Errors
from parse import parse


# TODO determine program path precisely
program_path = '.'


debug = False


# Build a program represented as a string (programText). A single call to
# Build performs semantic analysis and optionally type checking of the
# program *and* all imported modules, recursively. Return a 4-tuple containing
# the following items:
#
#   1. the annotated parse trees (one per file) of the program and dependant
#      modules
#   2. module map (map from module name to related MypyFile node)
#   3. the type info map (map from qualified type name to related TypeInfo;
#      includes each class and interface defined in the files)
#   4. node type map (map from parse tree node to its inferred type)
#
# Arguments:
#   programText: the contents of the main (program) source file
#   programFileName: the file name of the main source file, used for error
#     reporting (the default value is used by test cases only)
#   useTestBuiltins: if False, use normal builtins (default); if True, use
#     minimal stub builtins (this is for test cases only)
#   altLibDir: an additional directory for looking up library modules (takes
#     precedence over other directories)
#   doTypeCheck: if True, also perform type checking; otherwise, only perform
#     parsing and semantic analysis
#
# Currently the final pass of the build (the compiler back end) is not
# implemented yet.
tuple<list<MypyFile>, dict<str, MypyFile>, TypeInfoMap, dict<Node, Typ>> \
            build(str program_text, str program_file_name='main',
                  bool use_test_builtins=False, str alt_lib_path=None,
                  bool do_type_check=False):
    # Determine the default module search path.
    lib_path = default_lib_path()
    
    if use_test_builtins:
        # Use stub builtins (to speed up test cases and to make them easier to
        # debug).
        lib_path.insert(0, path_relative_to_program_path('test/data/lib-stub'))
    else:
        # Include directory of the program file in the module search path.
        lib_path.insert(0, fix_path(dirname(program_file_name)))
    
    # If provided, insert the caller-supplied extra module path to the
    # beginning (highest priority) of the search path.
    if alt_lib_path is not None:
        lib_path.insert(0, alt_lib_path)
    
    # Construct a build manager object that performs all the stages of the
    # build in the correct order.
    manager = BuildManager(lib_path, do_type_check)
    
    # Ignore current directory prefix in error messages.
    manager.errors.set_ignore_prefix(os.getcwd())
    
    # Construct information that describes the initial file. __main__ is the
    # implicit module id and there is no import context yet ([]).
    info = StateInfo(program_file_name, '__main__', [], manager)
    # Perform the build by sending the file as new file (UnprocessedFile is the
    # initial state of all files) to the manager. The manager will process the
    # file and all dependant modules recursively.
    return manager.process(UnprocessedFile(info, program_text))


# Return default standard library search paths.
list<str> default_lib_path():
    # IDEA: Make this more portable.
    list<str> path = []
    
    # Add MYPYPATH environment variable to library path, if defined.
    path_env = os.getenv('MYPYPATH')
    if path_env is not None:
        path.append(path_env)
    
    # Add library stubs directory.
    path.append(path_relative_to_program_path('stubs'))
    
    # Add fallback path that can be used if we have a broken installation.
    if platform != 'windows':
        path.append('/usr/local/lib/mypy')
    
    return path


# This is the central class for building a mypy program. It coordinates
# parsing, import processing, semantic analysis and type checking. It manages
# state objects that actually perform the build steps.
class BuildManager:
    bool do_type_check    # Do we perform a type check?
    list<str> lib_path    # Library path for looking up modules
    SemanticAnal sem_anal # Semantic analyzer
    TypeChecker checker   # Type checker
    Errors errors         # For reporting all errors
    
    # States of all individual files that are being processed. Each file in a
    # build is always represented by a single state object (after it has been
    # encountered for the first time). This is the only location for storing
    # all the states.
    list<State> states
    # Map from module name to source file path. There is a 1:1 mapping between
    # modules and source files.
    dict<str, str> module_files
    
    void __init__(self, list<str> lib_path, bool do_type_check):
        self.errors = Errors()
        self.lib_path = lib_path
        self.do_type_check = do_type_check
        self.sem_anal = SemanticAnal(lib_path, self.errors)
        self.checker = TypeChecker(self.errors, self.sem_anal.modules)
        self.states = []
        self.module_files = {}
    
    # Perform a build. The argument is a state that represents tha main program
    # file. This method should only be called once per a build manager object.
    # The return values are identical to the return values of Build.
    tuple<list<MypyFile>, dict<str, MypyFile>, TypeInfoMap, dict<Node, Typ>> \
                process(self, UnprocessedFile initial_state):
        self.states.append(initial_state)
        
        # Process states in a loop until all files (states) are finished.
        while True:
            # Find the next state that has all its dependencies met.
            next = self.next_available_state()
            if not next:
                trace('done')
                break
            
            # Potentially output some debug information.
            trace('next {} ({})'.format(next.path, next.state()))
            
            # Set the import context for reporting error messages correctly and
            # process the state. The process method is reponsible for adding a
            # new state object representing the new state of the file.
            self.errors.set_import_context(next.import_context)
            next.process()
        
        # Raise exception if the build failed.
        if self.errors.is_errors():
            self.errors.raise_error()
        
        # If there were no errors, all files should have been fully processed.
        for s in self.states:
            if s.state() != final_state:
                raise RuntimeError('{} still unprocessed'.format(s.path))
        
        # Collect a list of all files.
        list<MypyFile> trees = []
        for state in self.states:
            trees.append(((ParsedFile)state).tree)
        
        return (trees, self.sem_anal.modules, self.sem_anal.types,
                self.checker.type_map)
    
    # Find a ready state (one that has all its dependencies met).
    State next_available_state(self):
        i = len(self.states) - 1
        while i >= 0:
            if self.states[i].is_ready():
                return self.states[i]
            i -= 1
        return None
    
    # Have we seen a module yet?
    bool has_module(self, str name):
        return name in self.module_files
    
    # Return the state of a file. This does not consider any dependencies.
    int file_state(self, str path):
        for s in self.states:
            if s.path == path:
                return s.state()
        return UNSEEN_STATE
    
    # Return the state of a module. This considers also module dependencies.
    int module_state(self, str name):
        if not self.has_module(name):
            return UNSEEN_STATE
        state = final_state
        fs = self.file_state(self.module_files[name])
        if earlier_state(fs, state):
            state = fs
        return state
    
    # Return tuple (module id, line number of import) for all modules imported
    # in a file.
    # TODO also find imports not at the top level of the file
    list<tuple<str, int>> all_imported_modules(self, MypyFile file):
        list<tuple<str, int>> res = []
        for d in file.defs:
            if isinstance(d, Import):
                for id, _ in ((Import)d).ids:
                    res.append((id, d.line))
            elif isinstance(d, ImportFrom):
                imp = (ImportFrom)d
                res.append((imp.id, imp.line))
                # Also add any imported names that are submodules.
                for name, __ in imp.names:
                    sub_id = imp.id + '.' + name
                    if self.is_module(sub_id):
                        res.append((sub_id, imp.line))
            elif isinstance(d, ImportAll):
                res.append((((ImportAll)d).id, d.line))
        return res
    
    # Is there a file in the file system corresponding to the given module?
    bool is_module(self, str id):
        return find_module(id, self.lib_path) is not None


# Convert a path to a path relative to ProgramPath of the current program,
# independent of the working directory.
str path_relative_to_program_path(str dir):
    base_path = dirname(program_path)
    return fix_path(os.path.normpath(os.path.join(base_path, dir)))


# Remove current working directory prefix from p, if present. If the result
# would be empty, return '.' instead.
str fix_path(str p):
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


# State ids.
UNSEEN_STATE = 0
UNPROCESSED_STATE = 1
PARSED_STATE = 2
SEMANTICALLY_ANALYSED_STATE = 3
TYPE_CHECKED_STATE = 4


final_state = TYPE_CHECKED_STATE


state_order = [UNSEEN_STATE,
               UNPROCESSED_STATE,
               PARSED_STATE,
               SEMANTICALLY_ANALYSED_STATE,
               TYPE_CHECKED_STATE]


bool earlier_state(int s, int t):
    return state_order.index(s) < state_order.index(t)


# Description of a source file that is being built.
class StateInfo:
    # Path to the file
    str path
    # Module id (__main__ for the main program file)
    str id
    # The import trail that caused this module to be imported (path, line)
    # tuples
    list<tuple<str, int>> import_context
    # The manager that manages this build
    BuildManager manager
    
    void __init__(self, str path, str id, list<tuple<str, int>> import_context,
                  BuildManager manager):
        self.path = path
        self.id = id
        self.import_context = import_context
        self.manager = manager


# Abstract base class for build states. There is always at most one  state
# per source file.
class State:
    str path
    str id   # Module id
    list<tuple<str, int>> import_context
    BuildManager manager
    # Modules that this file directly depends on (in no particular order).
    list<str> dependencies
    
    void __init__(self, StateInfo info):
        self.path = info.path
        self.id = info.id
        self.import_context = info.import_context
        self.manager = info.manager
        self.dependencies = []
    
    StateInfo info(self):
        return StateInfo(self.path, self.id, self.import_context, self.manager)
    
    void process(self):
        raise RuntimeError('Not implemented')
    
    # Dependencies are met if all dependencies are at least in the same state
    # as this object (but not in the initial state).
    bool is_ready(self):
        for module_name in self.dependencies:
            state = self.manager.module_state(module_name)      
            if earlier_state(state,
                             self.state()) or state == UNPROCESSED_STATE:
                return False
        return True
    
    int state(self):
        raise RuntimeError('Not implemented')
    
    void switch_state(self, State state_object):
        for i in range(len(self.manager.states)):
            if self.manager.states[i].path == state_object.path:
                self.manager.states[i] = state_object
                return 
        raise RuntimeError('State for {} not found'.format(state_object.path))
    
    Errors errors(self):
        return self.manager.errors
    
    SemanticAnal sem_anal(self):
        return self.manager.sem_anal
    
    def checker(self):
        return self.manager.checker
    
    void fail(self, str path, int line, str msg):
        self.errors().set_file(path)
        self.errors().report(line, msg)


class UnprocessedFile(State):
    str program_text # Program text (or None to read from file)
    
    void __init__(self, StateInfo info, str program_text):
        super().__init__(info)
        self.program_text = program_text
        trace('waiting {}'.format(info.path))
        
        # Add surrounding package(s) as dependencies.
        for p in super_packages(self.id):
            if not self.import_module(p):
                self.fail(self.path, 1, "No module named '{}'".format(p))
            self.dependencies.append(p)
    
    # Parse the file, store global names and advance to the next state.
    void process(self):
        tree = self.parse(self.program_text, self.path)
        self.manager.sem_anal.modules[self.id] = tree
        
        if '.' in self.id:
            # Include module in the symbol table of the enclosing package.
            c = self.id.split('.')
            p = '.'.join(c[:-1])
            self.manager.sem_anal.modules[p].names[c[-1]] = SymbolTableNode(
                MODULE_REF, tree, p)
        
        if self.id != 'builtins':
            trace('import builtins')
            if not self.import_module('builtins'):
                self.fail(self.path, 1, 'Could not find builtins')
        
        for id, line in self.manager.all_imported_modules(tree):
            bool res
            self.errors().push_import_context(self.path, line)
            try:
                res = self.import_module(id)
            finally:
                self.errors().pop_import_context()
            if not res:
                self.fail(self.path, line, "No module named '{}'".format(id))
        
        self.sem_anal().anal_defs(tree.defs, self.path, self.id)
        tree.names = self.sem_anal().globals
        
        self.switch_state(ParsedFile(self.info(), tree))
    
    bool import_module(self, str id):
        # Do nothing if already compiled.
        if self.manager.has_module(id):
            return True
        
        path, text = module_source(id, self.manager.lib_path)
        if text is not None:
            info = StateInfo(path, id, self.errors().import_context(),
                             self.manager)
            self.manager.states.append(UnprocessedFile(info, text))
            self.manager.module_files[id] = path
            return True
        else:
            return False
    
    MypyFile parse(self, str s, str fnam):
        num_errs = self.errors().num_messages()
        tree = parse(s, fnam, self.errors())
        tree._full_name = self.id
        if self.errors().num_messages() != num_errs:
            self.errors().raise_error()
        return tree
    
    int state(self):
        return UNPROCESSED_STATE


class ParsedFile(State):
    MypyFile tree
    
    void __init__(self, StateInfo info, MypyFile tree):
        super().__init__(info)
        self.tree = tree
        
        list<str> imp = []
        for id, line in self.manager.all_imported_modules(tree):
            imp.append(id)
        if self.id != 'builtins':
            imp.append('builtins')
        
        if imp != []:
            trace('{} dependencies: {}'.format(info.path, imp))
        
        self.dependencies.extend(imp)
    
    # Semantically analyze file and advance to the next state.
    void process(self):
        self.sem_anal().visit_file(self.tree, self.tree.path)
        self.switch_state(SemanticallyAnalysedFile(self.info(), self.tree))
    
    int state(self):
        return PARSED_STATE


class SemanticallyAnalysedFile(ParsedFile):
    # Type check file and advance to the next state.
    void process(self):
        if self.manager.do_type_check:
            self.checker().visit_file(self.tree, self.tree.path)
        
        # FIX remove from active state list to speed up processing
        
        self.switch_state(TypeCheckedFile(self.info(), self.tree))
    
    int state(self):
        return SEMANTICALLY_ANALYSED_STATE


class TypeCheckedFile(SemanticallyAnalysedFile):
    # Finished, so cannot process.
    void process(self):
        raise RuntimeError('Cannot process TypeCheckedFile')
    
    # Finished, so cannot ever become ready.
    bool is_ready(self):
        return False
    
    int state(self):
        return TYPE_CHECKED_STATE


def trace(s):
    if debug:
        print(s)


# Find and read the source file of a module. Return a pair
# (path, file contents). Return (None, None) if the module could not be
# imported.
#
# id is a string of form "foo" or "foo.bar" (module name)
tuple<str, str> module_source(str id, list<str> paths):
    path = find_module(id, paths)
    if path is not None:
        str text
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


# Return that path of the module source file, or None if not found.
str find_module(str id, list<str> paths):
    for libpath in paths:
        comp = id.split('.')
        path = os.path.join(libpath, os.sep.join(comp[:-1]), comp[-1] + '.py')
        str text
        if not os.path.isfile(path):
            path = os.path.join(libpath, os.sep.join(comp), '__init__.py')
        if os.path.isfile(path) and verify_module(id, path):
            return path
    return None


def verify_module(id, path):
    # Check that all packages containing id have a __init__ file.
    if path.endswith('__init__.py'):
        path = dirname(path)
    for i in range(id.count('.')):
        path = dirname(path)
        if not os.path.isfile(os.path.join(path, '__init__.py')):
            return False
    return True


list<str> super_packages(str id):
    c = id.split('.')
    list<str> res = []
    for i in range(1, len(c)):
        res.append('.'.join(c[:i]))
    return res
