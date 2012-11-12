import os
import os.path
from nodes import MypyFile, Node, Import, ImportFrom, ImportAll
from semanal import TypeInfoMap, SemanticAnal
from types import Typ
from os import dir_name, base_name, separator
from sys import platform, program_path
from checker import TypeChecker
from errors import Errors


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
tuple<list<MypyFile>, dict<str, MypyFile>, TypeInfoMap, dict<Node, Typ>> build(str program_text, str program_file_name='main', bool use_test_builtins=False, str alt_lib_path=None, bool do_type_check=False):
    # Determine the default module search path.
    lib_path = default_lib_path()
    
    if use_test_builtins:
        # Use stub builtins (to speed up test cases and to make them easier to
        # debug).
        lib_path.insert(0, path_relative_to_program_path('test/data/lib-stub'))
    else:
        # Include directory of the program file in the module search path.
        lib_path.insert(0, fix_path(dir_name(program_file_name)))
    
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
    bool do_type_check      # Do we perform a type check?
    list<str> lib_path   # Library path for looking up modules
    SemanticAnal sem_anal # Semantic analyzer
    TypeChecker checker  # Type checker
    Errors errors = Errors()   # For reporting all errors
    
    # States of all individual files that are being processed. Each file in a
    # build is always represented by a single state object (after it has been
    # encountered for the first time). This is the only location for storing
    # all the states.
    list<State> states = []
    # Map from module name to source file path. There is a 1:1 mapping between
    # modules and source files.
    dict<str, str> module_files = {}
    
    void __init__(self, list<str> lib_path, bool do_type_check):
        self.lib_path = lib_path
        self.do_type_check = do_type_check
        self.sem_anal = SemanticAnal(lib_path, self.errors)
        self.checker = TypeChecker(self.errors, self.sem_anal.modules)
    
    # Perform a build. The argument is a state that represents tha main program
    # file. This method should only be called once per a build manager object.
    # The return values are identical to the return values of Build.
    tuple<list<MypyFile>, dict<str, MypyFile>, TypeInfoMap, dict<Node, Typ>> process(self, UnprocessedFile initial_state):
        self.states.append(initial_state)
        
        # Process states in a loop until all files (states) are finished.
        while True:
            # Find the next state that has all its dependencies met.
            next = self.next_available_state()
            if next is None:
                break
            
            # Potentially output some debug information.
            trace('next {} ({})'.format(next.path, next.state))
            
            # Set the import context for reporting error messages correctly and
            # process the state. The process method is reponsible for adding a new
            # state object representing the new state of the file.
            self.errors.set_import_context(next.import_context)
            next.process()
        
        # Raise exception if the build failed.
        if self.errors.is_errors():
            self.errors.raise_error()
        
        # If there were no errors, all files should have been fully processed.
        for s in self.states:
            if s.state != final_state:
                raise RuntimeError('{} still unprocessed'.format(s.path))
        
        # Collect a list of all files.
        list<MypyFile> trees = []
        for state in self.states:
            trees.append(((ParsedFile)state).tree)
        
        return trees, self.sem_anal.modules, self.sem_anal.types, self.checker.type_map
    
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
        return self.module_files.has_key(name)
    
    # Return the state of a file. This does not consider any dependencies.
    Constant file_state(self, str path):
        for s in self.states:
            if s.path == path:
                return s.state
        return UNSEEN_STATE
    
    # Return the state of a module. This considers also module dependencies.
    Constant module_state(self, str name):
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
                for name, _ in imp.names:
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
    base_path = dir_name(program_path)
    return fix_path(os.path.normpath(os.path.join(base_path, dir)))


# Remove current working directory prefix from p, if present. If the result
# would be empty, return '.' instead.
str fix_path(str p):
    cur = os.getcwd()
    # Add separator to the end of the path, unless one is already present.
    if base_name(cur) != '':
        cur += separator
    # Remove current directory prefix from the path, if present.
    if p.startswith(cur):
        p = p[len(cur):]
    # Avoid returning an empty path; replace that with '.'.
    if p == '':
        p = '.'
    return p
