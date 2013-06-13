"""The semantic analyzer.

Bind names to definitions and do various other simple consistency
checks. Semantic analysis is the first analysis pass after parsing,
and it is subdivided into two phases (implemented in FirstPass and
SemanticAnalyzer).
"""

from mypy.nodes import (
    MypyFile, TypeInfo, Node, AssignmentStmt, FuncDef, OverloadedFuncDef,
    TypeDef, VarDef, Var, GDEF, MODULE_REF, FuncItem, Import,
    ImportFrom, ImportAll, Block, LDEF, NameExpr, MemberExpr,
    IndexExpr, ParenExpr, TupleExpr, ListExpr, ExpressionStmt, ReturnStmt,
    RaiseStmt, YieldStmt, AssertStmt, OperatorAssignmentStmt, WhileStmt,
    ForStmt, BreakStmt, ContinueStmt, IfStmt, TryStmt, WithStmt, DelStmt,
    GlobalDecl, SuperExpr, DictExpr, CallExpr, RefExpr, OpExpr, UnaryExpr,
    SliceExpr, CastExpr, TypeApplication, Context, SymbolTable,
    SymbolTableNode, TVAR, UNBOUND_TVAR, ListComprehension, GeneratorExpr,
    FuncExpr, MDEF, FuncBase, Decorator, SetExpr, UndefinedExpr, TypeVarExpr,
    ARG_POS, MroError, type_aliases
)
from mypy.visitor import NodeVisitor
from mypy.errors import Errors
from mypy.types import (
    NoneTyp, Callable, Overloaded, Instance, Type, TypeVar, Any, FunctionLike,
    UnboundType, TypeList, ErrorType, TypeVars, TypeVarDef, replace_self_type,
    TupleType
)
from mypy.nodes import function_type, implicit_module_attrs
from mypy.typeanal import TypeAnalyser


class TypeTranslationError(Exception):
    """Exception raised when an expression is not valid as a type."""


class SemanticAnalyzer(NodeVisitor):
    """Semantically analyze parsed mypy files.

    The analyzer binds names and does various consistency checks for a
    parse tree. Note that type checking is performed as a separate
    pass.

    This is the second phase of semantic analysis.
    """
    # Library search paths
    str[] lib_path
    # Module name space
    dict<str, MypyFile> modules
    # Global name space for current module
    SymbolTable globals
    # Names declared using "global" (separate set for each scope)
    set<str>[] global_decls
    # Class type variables (the scope is a single class definition)
    SymbolTable class_tvars
    # Local names of function scopes; None for non-function scopes.
    SymbolTable[] locals
    int[] block_depth   # Nested block depths of scopes
    TypeInfo type       # TypeInfo of enclosing class (or None)

    # Stack of outer classes (the second tuple item is tvar table).
    tuple<TypeInfo, SymbolTable>[] type_stack

    bool is_init_method # Are we now analysing __init__?
    bool is_function    # Are we now analysing a function/method?
    int loop_depth      # Depth of breakable loops
    str cur_mod_id      # Current module id (or None) (phase 2)
    set<str> imports    # Imported modules (during phase 2 analysis)
    Errors errors       # Keep track of generated errors
    
    void __init__(self, str[] lib_path, Errors errors):
        """Construct semantic analyzer.

        Use lib_path to search for modules, and report analysis errors
        using the Errors instance.
        """
        self.locals = [None]
        self.imports = set()
        self.type = None
        self.class_tvars = None
        self.type_stack = []
        self.block_depth = [0]
        self.loop_depth = 0
        self.lib_path = lib_path
        self.errors = errors
        self.modules = {}
        self.is_init_method = False
        self.is_function = False
    
    void visit_file(self, MypyFile file_node, str fnam):
        self.errors.set_file(fnam)
        self.globals = file_node.names
        self.cur_mod_id = file_node.fullname()
        
        if 'builtins' in self.modules:
            self.globals['__builtins__'] = SymbolTableNode(
                MODULE_REF, self.modules['builtins'], self.cur_mod_id)
        
        defs = file_node.defs
        for d in defs:
            d.accept(self)
    
    void visit_func_def(self, FuncDef defn):
        self.update_function_type_variables(defn)
        if self.is_class_scope():
            # Method definition
            defn.is_conditional = self.block_depth[-1] > 0
            defn.info = self.type
            if not defn.is_decorated:
                if not defn.is_overload:
                    if defn.name() in self.type.names:
                        n = self.type.names[defn.name()].node
                        if self.is_conditional_func(n, defn):
                            defn.original_def = (FuncDef)n
                        else:
                            self.name_already_defined(defn.name(), defn)
                    self.type.names[defn.name()] = SymbolTableNode(MDEF, defn)
            if defn.name() == '__init__':
                self.is_init_method = True
            if defn.args == []:
                self.fail('Method must have at least one argument', defn)
            elif defn.type:
                sig = (FunctionLike)defn.type
                defn.type = replace_implicit_self_type(sig,
                                                       self_type(self.type))

        if self.is_func_scope() and (not defn.is_decorated and
                                     not defn.is_overload):
            self.add_local_func(defn, defn)
            defn._fullname = defn.name()
        
        self.errors.push_function(defn.name())
        self.analyse_function(defn)
        self.errors.pop_function()
        self.is_init_method = False

    bool is_conditional_func(self, Node n, FuncDef defn):
        return (isinstance(n, FuncDef) and ((FuncDef)n).is_conditional and
                defn.is_conditional)

    void update_function_type_variables(self, FuncDef defn):
        """Make any type variables in the signature of defn explicit.

        Update the signature of defn to contain type variable definitions
        if defn is generic.
        """
        if defn.type:
            functype = (Callable)defn.type
            typevars = infer_type_variables(functype, self.globals)
            # Do not define a new type variable if already defined in scope.
            typevars = [tvar for tvar in typevars
                        if not self.is_defined_type_var(tvar, defn)]
            if typevars:
                defs = [TypeVarDef(name, -i - 1)
                        for i, name in enumerate(typevars)]
                functype.variables = TypeVars(defs)

    bool is_defined_type_var(self, str tvar, Node context):
        return self.lookup(tvar, context).kind == TVAR
    
    void visit_overloaded_func_def(self, OverloadedFuncDef defn):
        Callable[] t = []
        for decorator in defn.items:
            # TODO support decorated overloaded functions properly
            decorator.is_overload = True
            decorator.func.is_overload = True
            decorator.accept(self)
            t.append((Callable)function_type(decorator.func))
        defn.type = Overloaded(t)
        defn.type.line = defn.line
        
        if self.is_class_scope():
            self.type.names[defn.name()] = SymbolTableNode(MDEF, defn,
                                                           typ=defn.type)
            defn.info = self.type
        elif self.is_func_scope():
            self.add_local_func(defn, defn)
    
    void analyse_function(self, FuncItem defn):
        is_method = self.is_class_scope()
        self.enter()
        self.add_func_type_variables_to_symbol_table(defn)
        if defn.type:
            defn.type = self.anal_type(defn.type)
            if isinstance(defn, FuncDef):
                fdef = (FuncDef)defn
                fdef.info = self.type
                defn.type = set_callable_name(defn.type, fdef)
                if is_method and ((Callable)defn.type).arg_types != []:
                    ((Callable)defn.type).arg_types[0] = self_type(
                        fdef.info)
        for init in defn.init:
            if init:
                init.rvalue.accept(self)
        for v in defn.args:
            self.add_local(v, defn)
        for init_ in defn.init:
            if init_:
                init_.lvalues[0].accept(self)
        
        # The first argument of a method is like 'self', though the name could
        # be different.
        if is_method and defn.args:
            defn.args[0].is_self = True
        
        defn.body.accept(self)
        self.leave()
    
    void add_func_type_variables_to_symbol_table(self, FuncItem defn):
        if defn.type:
            tt = defn.type
            names = self.type_var_names()
            items = ((Callable)tt).variables.items
            for i in range(len(items)):
                name = items[i].name
                if name in names:
                    self.name_already_defined(name, defn)
                self.add_type_var(self.locals[-1], name, -i - 1)
                names.add(name)
    
    set<str> type_var_names(self):
        if not self.type:
            return set()
        else:
            return set(self.type.type_vars)
    
    void add_type_var(self, SymbolTable scope, str name, int id):
        scope[name] = SymbolTableNode(TVAR, None, None, None, id)
    
    void visit_type_def(self, TypeDef defn):
        self.setup_type_def_analysis(defn)
        self.analyze_base_classes(defn)

        # Analyze class body.
        defn.defs.accept(self)

        self.calculate_abstract_status(defn.info)
        
        # Restore analyzer state.
        self.block_depth.pop()
        self.locals.pop()
        self.type, self.class_tvars = self.type_stack.pop()
    
    void calculate_abstract_status(self, TypeInfo typ):
        """Calculate abstract status of a class.

        Set is_abstract of the type to True if the type has an unimplemented
        abstract attribute.  Also compute a list of abstract attributes.
        """
        concrete = set<str>()
        abstract = <str> []
        for base in typ.mro:
            for name, node in base.names.items():
                if isinstance(node.node, Decorator):
                    fdef = ((Decorator)node.node).func
                    if fdef.is_abstract and name not in concrete:
                        typ.is_abstract = True
                        abstract.append(name)
                concrete.add(name)
        typ.abstract_attributes = sorted(abstract)

    void clean_up_bases_and_infer_type_variables(self, TypeDef defn):
        """Remove extra base classes such as Generic and infer type vars.

        For example, consider this class:

        . class Foo(Bar, Generic[t]): ...

        Now we will remove Generic[t] from bases of Foo and infer that the
        type variable 't' is a type argument of Foo.
        """
        removed = <int> []
        type_vars = <TypeVarDef> []
        for i, base in enumerate(defn.base_types):
            # TODO bind name reliably
            if (isinstance(base, UnboundType)
                    and ((UnboundType)base).name in ('Generic',
                                                     'AbstractGeneric')):
                unbound = (UnboundType)base
                removed.append(i)
                for j, arg in enumerate(unbound.args):
                    type_vars.append(TypeVarDef(((UnboundType)arg).name,
                                                j + 1))
        if type_vars:
            defn.type_vars = TypeVars(type_vars)
        for i in reversed(removed):
            del defn.base_types[i]

    void setup_type_def_analysis(self, TypeDef defn):
        """Prepare for the analysis of a class definition."""
        if not defn.info:
            defn.info = TypeInfo(SymbolTable(), defn)
            defn.info._fullname = defn.info.name()
        if self.is_func_scope() or self.type:
            kind = MDEF
            if self.is_func_scope():
                kind = LDEF
            self.add_symbol(defn.name, SymbolTableNode(kind, defn.info), defn)
        # Remember previous active class and type variables.
        self.type_stack.append((self.type, self.class_tvars))        
        self.locals.append(None) # Add class scope
        self.block_depth.append(-1) # The class body increments this to 0
        self.type = defn.info
        self.add_class_type_variables_to_symbol_table(self.type)

    void analyze_base_classes(self, TypeDef defn):
        """Analyze and set up base classes."""        
        bases = <Instance> []
        for i in range(len(defn.base_types)):
            base = self.anal_type(defn.base_types[i])
            if isinstance(base, Instance):
                defn.base_types[i] = base
                bases.append((Instance)base)
        # Add 'object' as implicit base if there is no other base class.
        if (not defn.is_interface and not bases and
                defn.fullname != 'builtins.object'):
            obj = self.object_type()
            defn.base_types.insert(0, obj)
            bases.append(obj)
        defn.info.bases = bases
        if not self.verify_base_classes(defn):
            return
        try:
            defn.info.calculate_mro()
        except MroError:
            self.fail("Cannot determine consistent method resolution order "
                      '(MRO) for "%s"' % defn.name, defn)

    bool verify_base_classes(self, TypeDef defn):
        base_classes = <str> []
        info = defn.info
        for base in info.bases:
            baseinfo = base.type
            if self.is_base_class(info, baseinfo):
                self.fail('Cycle in inheritance hierarchy', defn)
                # Clear bases to forcefully get rid of the cycle.
                info.bases = []
            if baseinfo.fullname() in ['builtins.int',
                                       'builtins.bool',
                                       'builtins.float']:
                self.fail("'%s' is not a valid base class" %
                          baseinfo.name(), defn)
                return False
        dup = find_duplicate(info.direct_base_classes())
        if dup:
            self.fail('Duplicate base class "%s"' % dup.name(), defn)
            return False
        return True

    bool is_base_class(self, TypeInfo t, TypeInfo s):
        """Determine if t is a base class of s (but do not use mro)."""
        # Search the base class graph for t, starting from s.
        worklist = [s]
        visited = {s}
        while worklist:
            nxt = worklist.pop()
            if nxt == t:
                return True
            for base in nxt.bases:
                if base.type not in visited:
                    worklist.append(base.type)
                    visited.add(base.type)
        return False

    Instance object_type(self):
        return self.named_type('__builtins__.object')

    Instance named_type(self, str qualified_name):
        sym = self.lookup_qualified(qualified_name, None)
        return Instance((TypeInfo)sym.node, [])
    
    bool is_instance_type(self, Type t):
        return isinstance(t, Instance) and not ((Instance)t).type.is_interface
    
    void add_class_type_variables_to_symbol_table(self, TypeInfo info):
        self.class_tvars = SymbolTable()
        vars = info.type_vars
        if vars:
            for i in range(len(vars)):
                self.add_type_var(self.class_tvars, vars[i], i + 1)
    
    void visit_import(self, Import i):
        for id, as_id in i.ids:
            if as_id != id:
                m = self.modules[id]
                self.add_symbol(as_id, SymbolTableNode(MODULE_REF, m,
                                                       self.cur_mod_id), i)
            else:
                base = id.split('.')[0]
                m = self.modules[base]
                self.add_symbol(base, SymbolTableNode(MODULE_REF, m,
                                                      self.cur_mod_id), i)
    
    void visit_import_from(self, ImportFrom i):
        m = self.modules[i.id]
        for id, as_id in i.names:
            node = m.names.get(id, None)
            if node:
                node = self.normalize_type_alias(node, i)
                if not node:
                    return
                self.add_symbol(as_id, SymbolTableNode(node.kind, node.node,
                                                       self.cur_mod_id), i)
            else:
                self.fail("Module has no attribute '{}'".format(id), i)

    SymbolTableNode normalize_type_alias(self, SymbolTableNode node,
                                         Context ctx):
        if node.fullname() in type_aliases:
            # Node refers to an aliased type such as typing.List; normalize.
            node = self.lookup_qualified(type_aliases[node.fullname()], ctx)
        return node
    
    void visit_import_all(self, ImportAll i):
        m = self.modules[i.id]
        for name, node in m.names.items():
            if not name.startswith('_'):
                self.add_symbol(name, SymbolTableNode(node.kind, node.node,
                                                      self.cur_mod_id), i)
    
    #
    # Statements
    #
    
    void visit_block(self, Block b):
        self.block_depth[-1] += 1
        for s in b.body:
            s.accept(self)
        self.block_depth[-1] -= 1
    
    void visit_block_maybe(self, Block b):
        if b:
            self.visit_block(b)
    
    void visit_var_def(self, VarDef defn):
        for i in range(len(defn.items)):
            defn.items[i].type = self.anal_type(defn.items[i].type)
        
        for v in defn.items:
            if self.is_func_scope():
                defn.kind = LDEF
                self.add_local(v, defn)
            elif self.type:
                v.info = self.type
                v.is_initialized_in_class = defn.init is not None
                self.type.names[v.name()] = SymbolTableNode(MDEF, v,
                                                            typ=v.type)
            elif v.name not in self.globals:
                defn.kind = GDEF
                self.add_var(v, defn)
        
        if defn.init:
            defn.init.accept(self)
    
    Type anal_type(self, Type t):
        if t:
            a = TypeAnalyser(self.lookup_qualified, self.fail)
            return t.accept(a)
        else:
            return None
    
    void visit_assignment_stmt(self, AssignmentStmt s):
        for lval in s.lvalues:
            self.analyse_lvalue(lval, explicit_type=s.type is not None)
        s.rvalue.accept(self)
        if s.type:
            s.type = self.anal_type(s.type)
        else:
            s.type = self.infer_type_from_undefined(s.rvalue)
        if s.type:
            # Store type into nodes.
            for lvalue in s.lvalues:
                self.store_declared_types(lvalue, s.type)
    
    void analyse_lvalue(self, Node lval, bool nested=False,
                        bool add_global=False, bool explicit_type=False):
        """Analyze an lvalue or assignment target.

        Only if add_global is True, add name to globals table. If nested
        is true, the lvalue is within a tuple or list lvalue expression.
        """
        if isinstance(lval, NameExpr):
            n = (NameExpr)lval
            nested_global = (not self.is_func_scope() and
                             self.block_depth[-1] > 0 and
                             not self.type)
            if (add_global or nested_global) and n.name not in self.globals:
                # Define new global name.
                v = Var(n.name)
                v._fullname = self.qualified_name(n.name)
                v.is_ready = False # Type not inferred yet
                n.node = v
                n.is_def = True
                n.kind = GDEF
                n.fullname = v._fullname
                self.globals[n.name] = SymbolTableNode(GDEF, v,
                                                       self.cur_mod_id)
            elif isinstance(n.node, Var) and n.is_def:
                # Since the is_def flag is set, this must have been analyzed
                # already in the first pass and added to the symbol table.
                v = (Var)n.node
                assert v.name() in self.globals
            elif (self.is_func_scope() and n.name not in self.locals[-1] and
                  n.name not in self.global_decls[-1]):
                # Define new local name.
                v = Var(n.name)
                n.node = v
                n.is_def = True
                n.kind = LDEF
                self.add_local(v, n)
            elif not self.is_func_scope() and (self.type and
                                               n.name not in self.type.names):
                # Define a new attribute within class body.
                v = Var(n.name)
                v.info = self.type
                v.is_initialized_in_class = True
                n.node = v
                n.is_def = True
                self.type.names[n.name] = SymbolTableNode(MDEF, v)
            else:
                # Bind to an existing name.
                if explicit_type:
                    self.name_already_defined(n.name, lval)
                n.accept(self)
                self.check_lvalue_validity(n.node, n)
        elif isinstance(lval, MemberExpr):
            memberexpr = (MemberExpr)lval
            if not add_global:
                self.analyse_member_lvalue(memberexpr)
            if explicit_type and not self.is_self_member_ref(memberexpr):
                self.fail('Type cannot be declared in assignment to non-self '
                          'attribute', lval)
        elif isinstance(lval, IndexExpr):
            if explicit_type:
                self.fail('Unexpected type declaration', lval)
            if not add_global:
                lval.accept(self)
        elif isinstance(lval, ParenExpr):
            self.analyse_lvalue(((ParenExpr)lval).expr, nested, add_global,
                                explicit_type)
        elif (isinstance(lval, TupleExpr) or
              isinstance(lval, ListExpr)) and not nested:
            items = ((any)lval).items
            for i in items:
                self.analyse_lvalue(i, nested=True, add_global=add_global,
                                    explicit_type = explicit_type)
        else:
            self.fail('Invalid assignment target', lval)
    
    void analyse_member_lvalue(self, MemberExpr lval):
        lval.accept(self)
        if self.is_init_method and (self.is_self_member_ref(lval) and
                                    lval.name not in self.type.names):
            # Implicit attribute definition in __init__.
            lval.is_def = True
            v = Var(lval.name)
            v.info = self.type
            v.is_ready = False
            lval.def_var = v
            lval.node = v
            self.type.names[lval.name] = SymbolTableNode(MDEF, v)
        self.check_lvalue_validity(lval.node, lval)

    bool is_self_member_ref(self, MemberExpr memberexpr):
        """Does memberexpr to refer to an attribute of self?"""
        if not isinstance(memberexpr.expr, NameExpr):
            return False
        node = ((NameExpr)memberexpr.expr).node
        return isinstance(node, Var) and ((Var)node).is_self

    void check_lvalue_validity(self, Node node, Context ctx):
        if (isinstance(node, FuncDef) or
                isinstance(node, TypeInfo)):
            self.fail('Invalid assignment target', ctx)

    Type infer_type_from_undefined(self, Node rvalue):
        if isinstance(rvalue, CallExpr):
            call = (CallExpr)rvalue
            if isinstance(call.analyzed, UndefinedExpr):
                undef = (UndefinedExpr)call.analyzed
                return undef.type
        return None

    void store_declared_types(self, Node lvalue, Type typ):
        if isinstance(lvalue, RefExpr):
            ref = (RefExpr)lvalue
            ref.is_def = False
            if isinstance(ref.node, Var):
                var = (Var)ref.node
                var.type = typ
                var.is_ready = True
            # If node is not a variable, we'll catch it elsewhere.
        elif isinstance(lvalue, TupleExpr):
            if isinstance(typ, TupleType):
                tuple_expr = (TupleExpr)lvalue
                tuple_type = (TupleType)typ
                if len(tuple_expr.items) != len(tuple_type.items):
                    self.fail('Incompatible number of tuple items', lvalue)
                    return
                for item, itemtype in zip(tuple_expr.items,
                                          tuple_type.items):
                    self.store_declared_types(item, itemtype)
            else:
                self.fail('Tuple type expected for multiple variables',
                          lvalue) 
        elif isinstance(lvalue, ParenExpr):
            paren = (ParenExpr)lvalue
            self.store_declared_types(paren.expr, typ)
        else:
            raise RuntimeError('Not implemented yet (%s)' % type(lvalue))

    void visit_decorator(self, Decorator dec):
        if not dec.is_overload:
            if self.is_func_scope():
                self.add_symbol(dec.var.name(), SymbolTableNode(LDEF, dec),
                                dec)
            elif self.type:
                dec.var.info = self.type
                dec.var.is_initialized_in_class = True
                self.add_symbol(dec.var.name(), SymbolTableNode(MDEF, dec),
                                dec)
        dec.func.accept(self)
        for d in dec.decorators:
            d.accept(self)
        for i, d in enumerate(dec.decorators):
            if refers_to_fullname(d, 'abc.abstractmethod'):
                dec.decorators.remove(d)
                dec.func.is_abstract = True
                if not self.type or self.is_func_scope():
                    self.fail("'abstractmethod' used with a non-method", dec)
                break
    
    void visit_expression_stmt(self, ExpressionStmt s):
        s.expr.accept(self)
    
    void visit_return_stmt(self, ReturnStmt s):
        if not self.is_func_scope():
            self.fail("'return' outside function", s)
        if s.expr:
            s.expr.accept(self)
    
    void visit_raise_stmt(self, RaiseStmt s):
        if s.expr:
            s.expr.accept(self)
    
    void visit_yield_stmt(self, YieldStmt s):
        if not self.is_func_scope():
            self.fail("'yield' outside function", s)
        if s.expr:
            s.expr.accept(self)
    
    void visit_assert_stmt(self, AssertStmt s):
        if s.expr:
            s.expr.accept(self)
    
    void visit_operator_assignment_stmt(self, OperatorAssignmentStmt s):
        s.lvalue.accept(self)
        s.rvalue.accept(self)
    
    void visit_while_stmt(self, WhileStmt s):
        s.expr.accept(self)
        self.loop_depth += 1
        s.body.accept(self)
        self.loop_depth -= 1
        self.visit_block_maybe(s.else_body)
    
    void visit_for_stmt(self, ForStmt s):
        s.expr.accept(self)
        
        # Bind index variables and check if they define new names.
        for n in s.index:
            self.analyse_lvalue(n)
        
        # Analyze index variable types.
        for i in range(len(s.types)):
            t = s.types[i]
            if t:
                s.types[i] = self.anal_type(t)
                v = (Var)s.index[i].node
                # TODO check if redefinition
                v.type = s.types[i]
        
        # Report error if only some of the loop variables have annotations.
        if s.types != [None] * len(s.types) and None in s.types:
            self.fail('Cannot mix unannotated and annotated loop variables', s)
            
        self.loop_depth += 1
        self.visit_block(s.body)
        self.loop_depth -= 1
        
        self.visit_block_maybe(s.else_body)
    
    void visit_break_stmt(self, BreakStmt s):
        if self.loop_depth == 0:
            self.fail("'break' outside loop", s)
    
    void visit_continue_stmt(self, ContinueStmt s):
        if self.loop_depth == 0:
            self.fail("'continue' outside loop", s)
    
    void visit_if_stmt(self, IfStmt s):
        for i in range(len(s.expr)):
            s.expr[i].accept(self)
            self.visit_block(s.body[i])
        self.visit_block_maybe(s.else_body)
    
    void visit_try_stmt(self, TryStmt s):
        self.analyze_try_stmt(s, self)

    void analyze_try_stmt(self, TryStmt s, NodeVisitor visitor,
                          bool add_global=False):
        s.body.accept(visitor)
        for type, var, handler in zip(s.types, s.vars, s.handlers):
            if type:
                type.accept(visitor)
            if var:
                self.analyse_lvalue(var, add_global=add_global)
            handler.accept(visitor)
        if s.else_body:
            s.else_body.accept(visitor)
        if s.finally_body:
            s.finally_body.accept(visitor)
    
    void visit_with_stmt(self, WithStmt s):
        for e in s.expr:
            e.accept(self)
        for n in s.name:
            if n:
                self.analyse_lvalue(n)
        self.visit_block(s.body)
    
    void visit_del_stmt(self, DelStmt s):
        s.expr.accept(self)
        if not isinstance(s.expr, IndexExpr):
            self.fail('Invalid delete target', s)
    
    void visit_global_decl(self, GlobalDecl g):
        for n in g.names:
            self.global_decls[-1].add(n)
    
    #
    # Expressions
    #
    
    void visit_name_expr(self, NameExpr expr):
        n = self.lookup(expr.name, expr)
        if n:
            if n.kind == TVAR:
                self.fail("'{}' is a type variable and only valid in type "
                          "context".format(expr.name), expr)
            else:
                expr.kind = n.kind
                expr.node = ((Node)n.node)
                expr.fullname = n.fullname()
    
    void visit_super_expr(self, SuperExpr expr):
        if not self.type:
            self.fail('"super" used outside class', expr)
            return 
        expr.info = self.type
    
    void visit_tuple_expr(self, TupleExpr expr):
        for item in expr.items:
            item.accept(self)
        if expr.types:
            for i in range(len(expr.types)):
                expr.types[i] = self.anal_type(expr.types[i])
    
    void visit_list_expr(self, ListExpr expr):
        for item in expr.items:
            item.accept(self)
        expr.type = self.anal_type(expr.type)
    
    void visit_set_expr(self, SetExpr expr):
        for item in expr.items:
            item.accept(self)
        expr.type = self.anal_type(expr.type)
    
    void visit_dict_expr(self, DictExpr expr):
        for key, value in expr.items:
            key.accept(self)
            value.accept(self)
        expr.key_type = self.anal_type(expr.key_type)
        expr.value_type = self.anal_type(expr.value_type)
    
    void visit_paren_expr(self, ParenExpr expr):
        expr.expr.accept(self)
    
    void visit_call_expr(self, CallExpr expr):
        """Analyze a call expression.

        Some call expressions are recognized as special forms, including
        cast(...), Undefined(...) and Any(...).
        """
        expr.callee.accept(self)
        if refers_to_fullname(expr.callee, 'typing.cast'):
            # Special form cast(...).
            if not self.check_fixed_args(expr, 2, 'cast'):
                return
            # Translate first argument to an unanalyzed type.
            try:
                target = expr_to_unanalyzed_type(expr.args[0])
            except TypeTranslationError:
                self.fail('Cast target is not a type', expr)
                return
            # Pigguback CastExpr object to the CallExpr object; it takes
            # precedence over the CallExpr semantics.
            expr.analyzed = CastExpr(expr.args[1], target)
            expr.analyzed.line = expr.line
            expr.analyzed.accept(self)
        elif refers_to_fullname(expr.callee, 'typing.Any'):
            # Special form Any(...).
            if not self.check_fixed_args(expr, 1, 'Any'):
                return            
            expr.analyzed = CastExpr(expr.args[0], Any())
            expr.analyzed.line = expr.line
            expr.analyzed.accept(self)
        elif refers_to_fullname(expr.callee, 'typing.Undefined'):
            # Special form Undefined(...).
            if not self.check_fixed_args(expr, 1, 'Undefined'):
                return
            try:
                type = expr_to_unanalyzed_type(expr.args[0])
            except TypeTranslationError:
                self.fail('Argument to Undefined is not a type', expr)
                return
            expr.analyzed = UndefinedExpr(type)
            expr.analyzed.line = expr.line
            expr.analyzed.accept(self)
        else:
            # Normal call expression.
            for a in expr.args:
                a.accept(self)

    bool check_fixed_args(self, CallExpr expr, int numargs, str name):
        """Verify that expr has specified number of positional args.

        Return True if the arguments are valid.
        """
        s = 's'
        if numargs == 1:
            s = ''
        if len(expr.args) != numargs:
            self.fail("'%s' expects %d argument%s" % (name, numargs, s),
                      expr)
            return False
        if expr.arg_kinds != [ARG_POS] * numargs:
            self.fail("'%s' must be called with %s positional argument%s" %
                      (name, numargs, s), expr)
            return False
        return True
    
    void visit_member_expr(self, MemberExpr expr):
        base = expr.expr
        base.accept(self)
        # Bind references to module attributes.
        if isinstance(base, RefExpr) and ((RefExpr)base).kind == MODULE_REF:
            names = ((MypyFile)((RefExpr)base).node).names
            n = names.get(expr.name, None)
            if n:
                n = self.normalize_type_alias(n, expr)
                if not n:
                    return
                expr.kind = n.kind
                expr.fullname = n.fullname()
                expr.node = n.node
    
    void visit_op_expr(self, OpExpr expr):
        expr.left.accept(self)
        expr.right.accept(self)
    
    void visit_unary_expr(self, UnaryExpr expr):
        expr.expr.accept(self)
    
    void visit_index_expr(self, IndexExpr expr):
        expr.base.accept(self)
        if refers_to_class_or_function(expr.base):
            # Special form -- type application.
            # Translate index to an unanalyzed type.
            types = <Type> []
            if isinstance(expr.index, TupleExpr):
                items = ((TupleExpr)expr.index).items
            else:
                items = [expr.index]
            for item in items:
                try:
                    typearg = expr_to_unanalyzed_type(item)
                except TypeTranslationError:
                    self.fail('Type expected within [...]', expr)
                    return
                typearg = self.anal_type(typearg)
                types.append(typearg)
            expr.analyzed = TypeApplication(expr.base, types)
            expr.analyzed.line = expr.line
        else:
            expr.index.accept(self)

    void visit_slice_expr(self, SliceExpr expr):
        if expr.begin_index:
            expr.begin_index.accept(self)
        if expr.end_index:
            expr.end_index.accept(self)
        if expr.stride:
            expr.stride.accept(self)
    
    void visit_cast_expr(self, CastExpr expr):
        expr.expr.accept(self)
        expr.type = self.anal_type(expr.type)

    void visit_undefined_expr(self, UndefinedExpr expr):
        expr.type = self.anal_type(expr.type)
    
    void visit_type_application(self, TypeApplication expr):
        expr.expr.accept(self)
        for i in range(len(expr.types)):
            expr.types[i] = self.anal_type(expr.types[i])

    void visit_list_comprehension(self, ListComprehension expr):
        expr.generator.accept(self)

    void visit_generator_expr(self, GeneratorExpr expr):
        self.enter()
        expr.right_expr.accept(self)
        # Bind index variables.
        for n in expr.index:
            self.analyse_lvalue(n)
        if expr.condition:
            expr.condition.accept(self)

        # TODO analyze variable types (see visit_for_stmt)

        expr.left_expr.accept(self)
        self.leave()

    void visit_func_expr(self, FuncExpr expr):
        self.analyse_function(expr)
    
    #
    # Helpers
    #
    
    SymbolTableNode lookup(self, str name, Context ctx):
        """Look up an unqualified name in all active namespaces."""
        # 1. Name declared using 'global x' takes precedence
        if name in self.global_decls[-1]:
            if name in self.globals:
                return self.globals[name]
            else:
                self.name_not_defined(name, ctx)
                return None
        # 2. Class tvars and class attributes (if inside type def)
        if self.class_tvars and name in self.class_tvars:
            return self.class_tvars[name]
        if self.is_class_scope() and name in self.type.names:
            return self.type[name]
        # 3. Local (function) scopes
        for table in reversed(self.locals):
            if table is not None and name in table:
                return table[name]
        # 4. Current file global scope
        if name in self.globals:
            return self.globals[name]
        # 5. Builtins
        b = self.globals.get('__builtins__', None)
        if b:
            table = ((MypyFile)b.node).names
            if name in table:
                return table[name]
        # Give up.
        self.name_not_defined(name, ctx)
        return None
    
    SymbolTableNode lookup_qualified(self, str name, Context ctx):
        if '.' not in name:
            return self.lookup(name, ctx)
        else:
            parts = name.split('.')
            SymbolTableNode n = self.lookup(parts[0], ctx)
            if n:
                for i in range(1, len(parts)):
                    if isinstance(n.node, TypeInfo):
                        n = ((TypeInfo)n.node).get(parts[i])
                    elif isinstance(n.node, MypyFile):
                        n = ((MypyFile)n.node).names.get(parts[i], None)
                    if not n:
                        self.name_not_defined(name, ctx)
                if n:
                    n = self.normalize_type_alias(n, ctx)
            return n
    
    str qualified_name(self, str n):
        return self.cur_mod_id + '.' + n
    
    void enter(self):
        self.locals.append(SymbolTable())
        self.global_decls.append(set())
    
    void leave(self):
        self.locals.pop()
        self.global_decls.pop()

    bool is_func_scope(self):
        return self.locals[-1] is not None

    bool is_class_scope(self):
        return self.type is not None and not self.is_func_scope()

    void add_symbol(self, str name, SymbolTableNode node, Context context):
        if self.is_func_scope():
            if name in self.locals[-1]:
                self.name_already_defined(name, context)
            self.locals[-1][name] = node
        elif self.type:
            self.type.names[name] = node
        else:
            if name in self.globals and not isinstance(node.node, MypyFile):
                # Modules can be imported multiple times to support import
                # of multiple submodules of a package (e.g. a.x and a.y).
                self.name_already_defined(name, context)
            self.globals[name] = node
    
    void add_var(self, Var v, Context ctx):
        if self.is_func_scope():
            self.add_local(v, ctx)
        else:
            self.globals[v.name()] = SymbolTableNode(GDEF, v, self.cur_mod_id)
            v._fullname = self.qualified_name(v.name())
    
    void add_local(self, Var v, Context ctx):
        if v.name() in self.locals[-1]:
            self.name_already_defined(v.name(), ctx)
        v._fullname = v.name()
        self.locals[-1][v.name()] = SymbolTableNode(LDEF, v)

    void add_local_func(self, FuncBase defn, Context ctx):
        # TODO combine with above
        if defn.name() in self.locals[-1]:
            self.name_already_defined(defn.name(), ctx)
        self.locals[-1][defn.name()] = SymbolTableNode(LDEF, defn)
    
    void check_no_global(self, str n, Context ctx, bool is_func=False):
        if n in self.globals:
            if is_func and isinstance(self.globals[n].node, FuncDef):
                self.fail(("Name '{}' already defined (overload variants "
                           "must be next to each other)").format(n), ctx)
            else:
                self.name_already_defined(n, ctx)
    
    void name_not_defined(self, str name, Context ctx):
        self.fail("Name '{}' is not defined".format(name), ctx)
    
    void name_already_defined(self, str name, Context ctx):
        self.fail("Name '{}' already defined".format(name), ctx)
    
    void fail(self, str msg, Context ctx):
        self.errors.report(ctx.get_line(), msg)


class FirstPass(NodeVisitor):
    """First phase of semantic analysis"""
    
    void __init__(self, SemanticAnalyzer sem):
        self.sem = sem

    void analyze(self, MypyFile file, str fnam, str mod_id):
        """Perform the first analysis pass.

        Resolve the full names of definitions not nested within functions and
        construct type info structures, but do not resolve inter-definition
        references such as base classes.

        Also add implicit definitions such as __name__.
        """
        sem = self.sem
        sem.cur_mod_id = mod_id
        sem.errors.set_file(fnam)
        sem.globals = SymbolTable()
        sem.global_decls = [set()]
        sem.block_depth = [0]

        defs = file.defs
    
        # Add implicit definitions of module '__name__' etc.
        for n in implicit_module_attrs:
            name_def = VarDef([Var(n, Any())], True)
            defs.insert(0, name_def)
        
        for d in defs:
            d.accept(self)
        
        # Add implicit definition of 'None' to builtins, as we cannot define a
        # variable with a None type explicitly.
        if mod_id == 'builtins':
            none_def = VarDef([Var('None', NoneTyp())], True)
            defs.append(none_def)
            none_def.accept(self)

    void visit_block(self, Block b):
        self.sem.block_depth[-1] += 1
        for node in b.body:
            node.accept(self)
        self.sem.block_depth[-1] -= 1
    
    void visit_assignment_stmt(self, AssignmentStmt s):
        for lval in s.lvalues:
            self.sem.analyse_lvalue(lval, add_global=True,
                                    explicit_type=s.type is not None)

        self.process_typevar_declaration(s)

    void process_typevar_declaration(self, AssignmentStmt s):
        """Check if s declares a typevar; it yes, store it in symbol table."""
        if len(s.lvalues) != 1 or not isinstance(s.lvalues[0], NameExpr):
            return
        if not isinstance(s.rvalue, CallExpr):
            return
        call = (CallExpr)s.rvalue
        if not isinstance(call.callee, NameExpr):
            return
        callee = (NameExpr)call.callee
        if callee.name != 'typevar':
            return
        # Yes, it's a type variable definition!
        name = ((NameExpr)s.lvalues[0]).name
        node = self.sem.globals[name]
        node.kind = UNBOUND_TVAR
        call.analyzed = TypeVarExpr()
        call.analyzed.line = call.line
    
    void visit_func_def(self, FuncDef d):
        sem = self.sem
        d.is_conditional = sem.block_depth[-1] > 0
        if d.name() in sem.globals:
            n = sem.globals[d.name()].node
            if sem.is_conditional_func(n, d):
                # Conditional function definition -- multiple defs are ok.
                d.original_def = (FuncDef)n
            else:
                sem.check_no_global(d.name(), d, True)
        d._fullname = sem.qualified_name(d.name())
        sem.globals[d.name()] = SymbolTableNode(GDEF, d, sem.cur_mod_id)
    
    void visit_overloaded_func_def(self, OverloadedFuncDef d):
        self.sem.check_no_global(d.name(), d)
        d._fullname = self.sem.qualified_name(d.name())
        self.sem.globals[d.name()] = SymbolTableNode(GDEF, d,
                                                     self.sem.cur_mod_id)
    
    void visit_type_def(self, TypeDef d):
        self.sem.clean_up_bases_and_infer_type_variables(d)
        self.sem.check_no_global(d.name, d)
        d.fullname = self.sem.qualified_name(d.name)
        info = TypeInfo(SymbolTable(), d)
        info.set_line(d.line)
        d.info = info
        self.sem.globals[d.name] = SymbolTableNode(GDEF, info,
                                                   self.sem.cur_mod_id)
        for defn in d.defs.body:
            if isinstance(defn, TypeDef):
                self.sem.clean_up_bases_and_infer_type_variables(
                    (TypeDef)defn)
    
    void visit_var_def(self, VarDef d):
        for v in d.items:
            self.sem.check_no_global(v.name(), d)
            v._fullname = self.sem.qualified_name(v.name())
            self.sem.globals[v.name()] = SymbolTableNode(GDEF, v,
                                                         self.sem.cur_mod_id)

    void visit_for_stmt(self, ForStmt s):
        for n in s.index:
            self.sem.analyse_lvalue(n, add_global=True)

    void visit_with_stmt(self, WithStmt s):
        for n in s.name:
            if n:
                self.sem.analyse_lvalue(n, add_global=True)

    void visit_decorator(self, Decorator d):
        d.var._fullname = self.sem.qualified_name(d.var.name())
        self.sem.add_symbol(d.var.name(), SymbolTableNode(GDEF, d.var), d)

    void visit_if_stmt(self, IfStmt s):
        for node in s.body:
            node.accept(self)
        if s.else_body:
            s.else_body.accept(self)

    void visit_try_stmt(self, TryStmt s):
        self.sem.analyze_try_stmt(s, self, add_global=True)


Instance self_type(TypeInfo typ):
    """For a non-generic type, return instance type representing the type.
    For a generic G type with parameters T1, .., Tn, return G<T1, ..., Tn>.
    """
    Type[] tv = []
    for i in range(len(typ.type_vars)):
        tv.append(TypeVar(typ.type_vars[i], i + 1))
    return Instance(typ, tv)


Callable replace_implicit_self_type(Callable sig, Type new):
    # We can detect implicit self type by it having no representation.
    if not sig.arg_types[0].repr:
        return replace_self_type(sig, new)
    else:
        return sig

FunctionLike replace_implicit_self_type(FunctionLike sig, Type new):
    osig = (Overloaded)sig
    return Overloaded([replace_implicit_self_type(i, new)
                       for i in osig.items()])


Type set_callable_name(Type sig, FuncDef fdef):
    if isinstance(sig, FunctionLike):
        if fdef.info:
            return ((FunctionLike)sig).with_name(
                '"{}" of "{}"'.format(fdef.name(), fdef.info.name()))
        else:
            return ((FunctionLike)sig).with_name(
                '"{}"'.format(fdef.name()))
    else:
        return sig


bool refers_to_fullname(Node node, str fullname):
    """Is node a name or member expression with the given full name?"""
    return isinstance(node,
                      RefExpr) and ((RefExpr)node).fullname == fullname


bool refers_to_class_or_function(Node node):
    """Does semantically analyzed node refer to a class?"""
    return (isinstance(node, RefExpr) and
            isinstance(((RefExpr)node).node, (TypeInfo, FuncDef,
                                              OverloadedFuncDef)))


Type expr_to_unanalyzed_type(Node expr):
    """Translate an expression to the corresonding type.

    The result is not semantically analyzed. It can be UnboundType or ListType.
    Raise TypeTranslationError if the expression cannot represent a type.
    """
    if isinstance(expr, NameExpr):
        name = ((NameExpr)expr).name
        return UnboundType(name, line=expr.line)
    elif isinstance(expr, MemberExpr):
        memberexpr = (MemberExpr)expr
        fullname = get_member_expr_fullname(memberexpr)
        if fullname:
            return UnboundType(fullname, line=expr.line)
        else:
            raise TypeTranslationError()
    elif isinstance(expr, IndexExpr):
        indexexpr = (IndexExpr)expr
        base = expr_to_unanalyzed_type(indexexpr.base)
        if isinstance(base, UnboundType):
            basetype = (UnboundType)base
            if basetype.args:
                raise TypeTranslationError()
            if isinstance(indexexpr.index, TupleExpr):
                args = ((TupleExpr)indexexpr.index).items
            else:
                args = [indexexpr.index]
            basetype.args = [expr_to_unanalyzed_type(arg) for arg in args]
            return basetype
        else:
            raise TypeTranslationError()
    elif isinstance(expr, ListExpr):
        lst = (ListExpr)expr
        return TypeList([expr_to_unanalyzed_type(t) for t in lst.items],
                        line=expr.line)
    else:
        raise TypeTranslationError()


str get_member_expr_fullname(MemberExpr expr):
    """Return the qualified name represention of a member expression.

    Return a string of form foo.bar, foo.bar.baz, or similar, or None if the
    argument cannot be represented in this form.
    """
    if isinstance(expr.expr, NameExpr):
        initial = ((NameExpr)expr.expr).name
    elif isinstance(expr.expr, MemberExpr):
        initial = get_member_expr_fullname((MemberExpr)expr.expr)
    else:
        return None
    return '{}.{}'.format(initial, expr.name)


str[] infer_type_variables(Callable type, SymbolTable globals):
    """Return list of unique type variables referred to in a callable type."""
    # TODO support multiple scopes
    result = <str> []
    for arg in type.arg_types + [type.ret_type]:
        for tvar in find_type_variables_in_type(arg, globals):
            if tvar not in result:
                result.append(tvar)
    return result


str[] find_type_variables_in_type(Type type, SymbolTable globals):
    """Return a list of all unique type variable references in type."""
    result = <str> []
    if isinstance(type, UnboundType):
        unbound = (UnboundType)type
        name = unbound.name
        if name in globals and globals[name].kind == UNBOUND_TVAR:
            result.append(name)
        for arg in unbound.args:
            result.extend(find_type_variables_in_type(arg, globals))
    elif isinstance(type, TypeList):
        types = (TypeList)type
        for item in types.items:
            result.extend(find_type_variables_in_type(item, globals))
    elif isinstance(type, Any):
        pass
    else:
        assert False, 'Unsupported type %s' % type
    return result


T find_duplicate<T>(T[] list):
    """If the list has duplicates, return one of the duplicates.

    Otherwise, return None.
    """
    for i in range(1, len(list)):
        if list[i] in list[:i]:
            return list[i]
    return None
