from errors import Errors
from semanal import SemanticAnal
from nodes import SymbolTableNode, MODULE_REF, MypyFile
from parser import parse


# State ids.
any UNSEEN_STATE, any UNPROCESSED_STATE, any PARSED_STATE, any SEMANTICALLY_ANALYSED_STATE, any TYPE_CHECKED_STATE


Constant final_state = TYPE_CHECKED_STATE


debug = False


list<Constant> state_order = [UNSEEN_STATE, UNPROCESSED_STATE, PARSED_STATE, SEMANTICALLY_ANALYSED_STATE, TYPE_CHECKED_STATE]


bool earlier_state(Constant s, Constant t):
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
    
    void __init__(self, str path, str id, list<tuple<str, int>> import_context, BuildManager manager):
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
    list<str> dependencies = []
    
    void __init__(self, StateInfo info):
        self.path = info.path
        self.id = info.id
        self.import_context = info.import_context
        self.manager = info.manager
    
    StateInfo info(self):
        return StateInfo(self.path, self.id, self.import_context, self.manager)
    
    void process(self):
        raise RuntimeError('Not implemented')
    
    # Dependencies are met if all dependencies are at least in the same state
    # as this object (but not in the initial state).
    bool is_ready(self):
        for module_name in self.dependencies:
            state = self.manager.module_state(module_name)      
            if earlier_state(state, self.state) or state == UNPROCESSED_STATE:
                return False
        return True
    
    @property
    Constant state():
        raise RuntimeError('Not implemented')
    
    void switch_state(self, State state_object):
        for i in range(len(self.manager.states)):
            if self.manager.states[i].path == state_object.path:
                self.manager.states[i] = state_object
                return 
        raise RuntimeError('State for {} not found'.format(state_object.path))
    
    @property
    Errors errors():
        return self.manager.errors
    
    @property
    SemanticAnal sem_anal():
        return self.manager.sem_anal
    
    @property
    def checker():
        return self.manager.checker
    
    void fail(self, str path, int line, str msg):
        self.errors.set_file(path)
        self.errors.report(line, msg)


class UnprocessedFile(State):
    str program_text # Program text (or nil to read from file)
    
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
            self.manager.sem_anal.modules[p].names[c[-1]] = SymbolTableNode(MODULE_REF, tree, p)
        
        if self.id != 'builtins':
            trace('import builtins')
            if not self.import_module('builtins'):
                self.fail(self.path, 1, 'Could not find builtins')
        
        for id, line in self.manager.all_imported_modules(tree):
            bool res
            self.errors.push_import_context(self.path, line)
            try:
                res = self.import_module(id)
            finally:
                self.errors.pop_import_context()
            if not res:
                self.fail(self.path, line, "No module named '{}'".format(id))
        
        self.sem_anal.anal_defs(tree.defs, self.path, self.id)
        tree.names = self.sem_anal.globals
        
        self.switch_state(ParsedFile(self.info(), tree))
    
    bool import_module(self, str id):
        # Do nothing if already compiled.
        if self.manager.has_module(id):
            return True
        
        path, text = module_source(id, self.manager.lib_path)
        if text is not None:
            info = StateInfo(path, id, self.errors.import_context(), self.manager)
            self.manager.states.append(UnprocessedFile(info, text))
            self.manager.module_files[id] = path
            return True
        else:
            return False
    
    MypyFile parse(self, str s, str fnam):
        num_errs = self.errors.num_messages()
        tree = parse(s, fnam, self.errors)
        tree.full_name = self.id
        if self.errors.num_messages() != num_errs:
            self.errors.raise_error()
        return tree
    
    @property
    Constant state():
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
        self.sem_anal.visit_file(self.tree, self.tree.path)
        
        self.switch_state(SemanticallyAnalysedFile(self.info(), self.tree))
    
    @property
    Constant state():
        return PARSED_STATE


class SemanticallyAnalysedFile(ParsedFile):
    # Type check file and advance to the next state.
    void process(self):
        if self.manager.do_type_check:
            self.checker.visit_file(self.tree, self.tree.path)
        
        # FIX remove from active state list to speed up processing
        
        self.switch_state(TypeCheckedFile(self.info(), self.tree))
    
    @property
    Constant state():
        return SEMANTICALLY_ANALYSED_STATE


class TypeCheckedFile(SemanticallyAnalysedFile):
    # Finished, so cannot process.
    void process(self):
        raise RuntimeError('Cannot process TypeCheckedFile')
    
    # Finished, so cannot ever become ready.
    bool is_ready(self):
        return False
    
    @property
    Constant state():
        return TYPE_CHECKED_STATE


def trace(s):
    if debug:
        print(s)
