"""The semantic analyzer.

Bind names to definitions and do various other simple consistency
checks. For example, consider this program:

  x = 1
  y = x

Here semantic analysis would detect that the assignment 'x = 1'
defines a new variable, the type of which is to be inferred (in a
later pass; type inference or type checking is not part of semantic
analysis).  Also, it would bind both references to 'x' to the same
module-level variable node.  The second assignment would also be
analyzed, and the type of 'y' marked as being inferred.

Semantic analysis is the first analysis pass after parsing, and it is
subdivided into three passes:

 * FirstPass looks up externally visible names defined in a module but
   ignores imports and local definitions.  It helps enable (some)
   cyclic references between modules, such as module 'a' that imports
   module 'b' and used names defined in b *and* vice versa.  The first
   pass can be performed before dependent modules have been processed.

 * SemanticAnalyzer is the second pass.  It does the bulk of the work.
   It assumes that dependent modules have been semantically analyzed,
   up to the second pass, unless there is a import cycle.

 * ThirdPass checks that type argument counts are valid; for example,
   it will reject Dict[int].  We don't do this in the second pass,
   since we infer the type argument counts of classes during this
   pass, and it is possible to refer to classes defined later in a
   file, which would not have the type argument count set yet.

Semantic analysis of types is implemented in module mypy.typeanal.

TODO: Check if the third pass slows down type checking significantly.
  We could probably get rid of it -- for example, we could collect all
  analyzed types in a collection and check them without having to
  traverse the entire AST.
"""

from typing import (
    Undefined, List, Dict, Set, Tuple, cast, Any, overload, typevar
)

from mypy.nodes import (
    MypyFile, TypeInfo, Node, AssignmentStmt, FuncDef, OverloadedFuncDef,
    ClassDef, VarDef, Var, GDEF, MODULE_REF, FuncItem, Import,
    ImportFrom, ImportAll, Block, LDEF, NameExpr, MemberExpr,
    IndexExpr, ParenExpr, TupleExpr, ListExpr, ExpressionStmt, ReturnStmt,
    RaiseStmt, YieldStmt, AssertStmt, OperatorAssignmentStmt, WhileStmt,
    ForStmt, BreakStmt, ContinueStmt, IfStmt, TryStmt, WithStmt, DelStmt,
    GlobalDecl, SuperExpr, DictExpr, CallExpr, RefExpr, OpExpr, UnaryExpr,
    SliceExpr, CastExpr, TypeApplication, Context, SymbolTable,
    SymbolTableNode, TVAR, UNBOUND_TVAR, ListComprehension, GeneratorExpr,
    FuncExpr, MDEF, FuncBase, Decorator, SetExpr, UndefinedExpr, TypeVarExpr,
    StrExpr, PrintStmt, ConditionalExpr, DucktypeExpr, DisjointclassExpr,
    ComparisonExpr, ARG_POS, ARG_NAMED, MroError, type_aliases
)
from mypy.visitor import NodeVisitor
from mypy.traverser import TraverserVisitor
from mypy.errors import Errors
from mypy.types import (
    NoneTyp, Callable, Overloaded, Instance, Type, TypeVar, AnyType,
    FunctionLike, UnboundType, TypeList, ErrorType, TypeVarDef,
    replace_leading_arg_type, TupleType, UnionType
)
from mypy.nodes import function_type, implicit_module_attrs
from mypy.typeanal import TypeAnalyser, TypeAnalyserPass3, analyse_node
from mypy.parsetype import parse_str_as_type, TypeParseError


T = typevar('T')


# Inferred value of an expression.
ALWAYS_TRUE = 0
ALWAYS_FALSE = 1
TRUTH_VALUE_UNKNOWN = 2


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
    lib_path = Undefined(List[str])
    # Module name space
    modules = Undefined(Dict[str, MypyFile])
    # Global name space for current module
    globals = Undefined(SymbolTable)
    # Names declared using "global" (separate set for each scope)
    global_decls = Undefined(List[Set[str]])
    # Local names of function scopes; None for non-function scopes.
    locals = Undefined(List[SymbolTable])
    # Nested block depths of scopes
    block_depth = Undefined(List[int])
    # TypeInfo of directly enclosing class (or None)
    type = Undefined(TypeInfo)
    # Stack of outer classes (the second tuple item contains tvars).
    type_stack = Undefined(List[Tuple[TypeInfo, List[SymbolTableNode]]])
    # Stack of functions being analyzed
    function_stack = Undefined(List[FuncItem])

    loop_depth = 0         # Depth of breakable loops
    cur_mod_id = ''        # Current module id (or None) (phase 2)
    imports = Undefined(Set[str])  # Imported modules (during phase 2 analysis)
    errors = Undefined(Errors)     # Keep track of generated errors

    def __init__(self, lib_path: List[str], errors: Errors,
                 pyversion: int = 3) -> None:
        """Construct semantic analyzer.

        Use lib_path to search for modules, and report analysis errors
        using the Errors instance.
        """
        self.locals = [None]
        self.imports = set()
        self.type = None
        self.type_stack = []
        self.function_stack = []
        self.block_depth = [0]
        self.loop_depth = 0
        self.lib_path = lib_path
        self.errors = errors
        self.modules = {}
        self.pyversion = pyversion
        self.stored_vars = Dict[Node, Type]()

    def visit_file(self, file_node: MypyFile, fnam: str) -> None:
        self.errors.set_file(fnam)
        self.globals = file_node.names
        self.cur_mod_id = file_node.fullname()

        if 'builtins' in self.modules:
            self.globals['__builtins__'] = SymbolTableNode(
                MODULE_REF, self.modules['builtins'], self.cur_mod_id)

        defs = file_node.defs
        for d in defs:
            d.accept(self)

        if self.cur_mod_id == 'builtins':
            remove_imported_names_from_symtable(self.globals, 'builtins')

    def visit_func_def(self, defn: FuncDef) -> None:
        self.errors.push_function(defn.name())
        self.update_function_type_variables(defn)
        self.errors.pop_function()

        if self.is_class_scope():
            # Method definition
            defn.is_conditional = self.block_depth[-1] > 0
            defn.info = self.type
            if not defn.is_decorated:
                if not defn.is_overload:
                    if defn.name() in self.type.names:
                        n = self.type.names[defn.name()].node
                        if self.is_conditional_func(n, defn):
                            defn.original_def = cast(FuncDef, n)
                        else:
                            self.name_already_defined(defn.name(), defn)
                    self.type.names[defn.name()] = SymbolTableNode(MDEF, defn)
            if not defn.is_static:
                if not defn.args:
                    self.fail('Method must have at least one argument', defn)
                elif defn.type:
                    sig = cast(FunctionLike, defn.type)
                    # TODO: A classmethod's first argument should be more
                    #       precisely typed than Any.
                    leading_type = AnyType() if defn.is_class else self_type(self.type)
                    defn.type = replace_implicit_first_type(sig, leading_type)

        if self.is_func_scope() and (not defn.is_decorated and
                                     not defn.is_overload):
            self.add_local_func(defn, defn)
            defn._fullname = defn.name()

        self.errors.push_function(defn.name())
        self.analyse_function(defn)
        self.errors.pop_function()

    def is_conditional_func(self, n: Node, defn: FuncDef) -> bool:
        return (isinstance(n, FuncDef) and cast(FuncDef, n).is_conditional and
                defn.is_conditional)

    def update_function_type_variables(self, defn: FuncDef) -> None:
        """Make any type variables in the signature of defn explicit.

        Update the signature of defn to contain type variable definitions
        if defn is generic.
        """
        if defn.type:
            functype = cast(Callable, defn.type)
            typevars = self.infer_type_variables(functype)
            # Do not define a new type variable if already defined in scope.
            typevars = [(tvar, values) for tvar, values in typevars
                        if not self.is_defined_type_var(tvar, defn)]
            if typevars:
                defs = [TypeVarDef(tvar[0], -i - 1, tvar[1], self.object_type())
                        for i, tvar in enumerate(typevars)]
                functype.variables = defs

    def infer_type_variables(self,
                             type: Callable) -> List[Tuple[str, List[Type]]]:
        """Return list of unique type variables referred to in a callable."""
        names = List[str]()
        values = List[List[Type]]()
        for arg in type.arg_types + [type.ret_type]:
            for tvar, vals in self.find_type_variables_in_type(arg):
                if tvar not in names:
                    names.append(tvar)
                    values.append(vals)
        return list(zip(names, values))

    def find_type_variables_in_type(
            self, type: Type) -> List[Tuple[str, List[Type]]]:
        """Return a list of all unique type variable references in type."""
        result = List[Tuple[str, List[Type]]]()
        if isinstance(type, UnboundType):
            name = type.name
            node = self.lookup_qualified(name, type)
            if node and node.kind == UNBOUND_TVAR:
                result.append((name, cast(TypeVarExpr, node.node).values))
            for arg in type.args:
                result.extend(self.find_type_variables_in_type(arg))
        elif isinstance(type, TypeList):
            for item in type.items:
                result.extend(self.find_type_variables_in_type(item))
        elif isinstance(type, UnionType):
            for item in type.items:
                result.extend(self.find_type_variables_in_type(item))
        elif isinstance(type, AnyType):
            pass
        else:
            assert False, 'Unsupported type %s' % type
        return result

    def is_defined_type_var(self, tvar: str, context: Node) -> bool:
        return self.lookup_qualified(tvar, context).kind == TVAR

    def visit_overloaded_func_def(self, defn: OverloadedFuncDef) -> None:
        t = List[Callable]()
        for item in defn.items:
            # TODO support decorated overloaded functions properly
            item.is_overload = True
            item.func.is_overload = True
            item.accept(self)
            t.append(cast(Callable, function_type(item.func,
                                                  self.builtin_type('builtins.function'))))
            if not [dec for dec in item.decorators
                    if refers_to_fullname(dec, 'typing.overload')]:
                self.fail("'overload' decorator expected", item)

        defn.type = Overloaded(t)
        defn.type.line = defn.line

        if self.is_class_scope():
            self.type.names[defn.name()] = SymbolTableNode(MDEF, defn,
                                                           typ=defn.type)
            defn.info = self.type
        elif self.is_func_scope():
            self.add_local_func(defn, defn)

    def analyse_function(self, defn: FuncItem) -> None:
        is_method = self.is_class_scope()
        tvarnodes = self.add_func_type_variables_to_symbol_table(defn)
        if defn.type:
            # Signature must be analyzed in the surrounding scope so that
            # class-level imported names and type variables are in scope.
            defn.type = self.anal_type(defn.type)
            self.check_function_signature(defn)
            if isinstance(defn, FuncDef):
                defn.info = self.type
                defn.type = set_callable_name(defn.type, defn)
        for init in defn.init:
            if init:
                init.rvalue.accept(self)
        self.function_stack.append(defn)
        self.enter()
        for v in defn.args:
            self.add_local(v, defn)
        for init_ in defn.init:
            if init_:
                init_.lvalues[0].accept(self)

        # The first argument of a non-static, non-class method is like 'self'
        # (though the name could be different), having the enclosing class's
        # instance type.
        if is_method and not defn.is_static and not defn.is_class and defn.args:
            defn.args[0].is_self = True

        defn.body.accept(self)
        disable_typevars(tvarnodes)
        self.leave()
        self.function_stack.pop()

    def add_func_type_variables_to_symbol_table(
            self, defn: FuncItem) -> List[SymbolTableNode]:
        nodes = List[SymbolTableNode]()
        if defn.type:
            tt = defn.type
            names = self.type_var_names()
            items = cast(Callable, tt).variables
            for i, item in enumerate(items):
                name = item.name
                if name in names:
                    self.name_already_defined(name, defn)
                node = self.add_type_var(name, -i - 1, defn)
                nodes.append(node)
                names.add(name)
        return nodes

    def type_var_names(self) -> Set[str]:
        if not self.type:
            return set()
        else:
            return set(self.type.type_vars)

    def add_type_var(self, fullname: str, id: int,
                     context: Context) -> SymbolTableNode:
        node = self.lookup_qualified(fullname, context)
        node.kind = TVAR
        node.tvar_id = id
        return node

    def check_function_signature(self, fdef: FuncItem) -> None:
        sig = cast(Callable, fdef.type)
        if len(sig.arg_types) < len(fdef.args):
            self.fail('Type signature has too few arguments', fdef)
        elif len(sig.arg_types) > len(fdef.args):
            self.fail('Type signature has too many arguments', fdef)

    def visit_class_def(self, defn: ClassDef) -> None:
        self.clean_up_bases_and_infer_type_variables(defn)
        self.setup_class_def_analysis(defn)
        self.analyze_base_classes(defn)
        self.analyze_metaclass(defn)

        for decorator in defn.decorators:
            self.analyze_class_decorator(defn, decorator)

        # Analyze class body.
        defn.defs.accept(self)

        self.calculate_abstract_status(defn.info)
        self.setup_ducktyping(defn)

        # Restore analyzer state.
        self.block_depth.pop()
        self.locals.pop()
        self.type, tvarnodes = self.type_stack.pop()
        disable_typevars(tvarnodes)
        if self.type_stack:
            # Enable type variables of the enclosing class again.
            enable_typevars(self.type_stack[-1][1])

    def analyze_class_decorator(self, defn: ClassDef, decorator: Node) -> None:
        decorator.accept(self)
        if refers_to_fullname(decorator, 'typing.builtinclass'):
            defn.is_builtinclass = True

    def calculate_abstract_status(self, typ: TypeInfo) -> None:
        """Calculate abstract status of a class.

        Set is_abstract of the type to True if the type has an unimplemented
        abstract attribute.  Also compute a list of abstract attributes.
        """
        concrete = Set[str]()
        abstract = List[str]()
        for base in typ.mro:
            for name, symnode in base.names.items():
                node = symnode.node
                if isinstance(node, OverloadedFuncDef):
                    # Unwrap an overloaded function definition. We can just
                    # check arbitrarily the first overload item. If the
                    # different items have a different abstract status, there
                    # should be an error reported elsewhere.
                    func = node.items[0]  # type: Node
                else:
                    func = node
                if isinstance(func, Decorator):
                    fdef = func.func
                    if fdef.is_abstract and name not in concrete:
                        typ.is_abstract = True
                        abstract.append(name)
                concrete.add(name)
        typ.abstract_attributes = sorted(abstract)

    def setup_ducktyping(self, defn: ClassDef) -> None:
        for decorator in defn.decorators:
            if isinstance(decorator, CallExpr):
                analyzed = decorator.analyzed
                if isinstance(analyzed, DucktypeExpr):
                    defn.info.ducktype = analyzed.type
                elif isinstance(analyzed, DisjointclassExpr):
                    node = analyzed.cls.node
                    if isinstance(node, TypeInfo):
                        defn.info.disjoint_classes.append(node)
                        defn.info.disjointclass_decls.append(node)
                        node.disjoint_classes.append(defn.info)
                    else:
                        self.fail('Argument 1 to disjointclass does not refer '
                                  'to a class', analyzed)

    def clean_up_bases_and_infer_type_variables(self, defn: ClassDef) -> None:
        """Remove extra base classes such as Generic and infer type vars.

        For example, consider this class:

        class Foo(Bar, Generic[T]): ...

        Now we will remove Generic[T] from bases of Foo and infer that the
        type variable 'T' is a type argument of Foo.
        """
        removed = List[int]()
        type_vars = List[TypeVarDef]()
        for i, base in enumerate(defn.base_types):
            tvars = self.analyze_typevar_declaration(base)
            if tvars is not None:
                if type_vars:
                    self.fail('Duplicate Generic or AbstractGeneric in bases',
                              defn)
                removed.append(i)
                for j, tvar in enumerate(tvars):
                    name, values = tvar
                    type_vars.append(TypeVarDef(name, j + 1, values,
                                                self.object_type()))
        if type_vars:
            defn.type_vars = type_vars
            if defn.info:
                defn.info.type_vars = [tv.name for tv in type_vars]
        for i in reversed(removed):
            del defn.base_types[i]

    def analyze_typevar_declaration(self, t: Type) -> List[Tuple[str,
                                                                 List[Type]]]:
        if not isinstance(t, UnboundType):
            return None
        unbound = cast(UnboundType, t)
        sym = self.lookup_qualified(unbound.name, unbound)
        if sym is None:
            return None
        if sym.node.fullname() in ('typing.Generic',
                                   'typing.AbstractGeneric'):
            tvars = List[Tuple[str, List[Type]]]()
            for arg in unbound.args:
                tvar = self.analyze_unbound_tvar(arg)
                if tvar:
                    tvars.append(tvar)
                else:
                    self.fail('Free type variable expected in %s[...]' %
                              sym.node.name(), t)
            return tvars
        return None

    def analyze_unbound_tvar(self, t: Type) -> Tuple[str, List[Type]]:
        if not isinstance(t, UnboundType):
            return None
        unbound = cast(UnboundType, t)
        sym = self.lookup_qualified(unbound.name, unbound)
        if sym is not None and sym.kind == UNBOUND_TVAR:
            return unbound.name, cast(TypeVarExpr, sym.node).values[:]
        return None

    def setup_class_def_analysis(self, defn: ClassDef) -> None:
        """Prepare for the analysis of a class definition."""
        if not defn.info:
            defn.info = TypeInfo(SymbolTable(), defn)
            defn.info._fullname = defn.info.name()
        if self.is_func_scope() or self.type:
            kind = MDEF
            if self.is_func_scope():
                kind = LDEF
            self.add_symbol(defn.name, SymbolTableNode(kind, defn.info), defn)
        if self.type_stack:
            # Disable type variables of the enclosing class.
            disable_typevars(self.type_stack[-1][1])
        tvarnodes = self.add_class_type_variables_to_symbol_table(defn.info)
        # Remember previous active class and type vars of *this* class.
        self.type_stack.append((self.type, tvarnodes))
        self.locals.append(None)  # Add class scope
        self.block_depth.append(-1)  # The class body increments this to 0
        self.type = defn.info

    def analyze_base_classes(self, defn: ClassDef) -> None:
        """Analyze and set up base classes."""
        bases = List[Instance]()
        for i in range(len(defn.base_types)):
            base = self.anal_type(defn.base_types[i])
            if isinstance(base, Instance):
                defn.base_types[i] = base
                bases.append(base)
        # Add 'object' as implicit base if there is no other base class.
        if (not bases and defn.fullname != 'builtins.object'):
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
        else:
            # If there are cyclic imports, we may be missing 'object' in
            # the MRO. Fix MRO if needed.
            if defn.info.mro[-1].fullname() != 'builtins.object':
                defn.info.mro.append(self.object_type().type)

    def verify_base_classes(self, defn: ClassDef) -> bool:
        base_classes = List[str]()
        info = defn.info
        for base in info.bases:
            baseinfo = base.type
            if self.is_base_class(info, baseinfo):
                self.fail('Cycle in inheritance hierarchy', defn)
                # Clear bases to forcefully get rid of the cycle.
                info.bases = []
            if baseinfo.fullname() == 'builtins.bool':
                self.fail("'%s' is not a valid base class" %
                          baseinfo.name(), defn)
                return False
        dup = find_duplicate(info.direct_base_classes())
        if dup:
            self.fail('Duplicate base class "%s"' % dup.name(), defn)
            return False
        return True

    def is_base_class(self, t: TypeInfo, s: TypeInfo) -> bool:
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

    def analyze_metaclass(self, defn: ClassDef) -> None:
        if defn.metaclass:
            sym = self.lookup_qualified(defn.metaclass, defn)
            if sym is not None and not isinstance(sym.node, TypeInfo):
                self.fail("Invalid metaclass '%s'" % defn.metaclass, defn)

    def object_type(self) -> Instance:
        return self.named_type('__builtins__.object')

    def named_type(self, qualified_name: str) -> Instance:
        sym = self.lookup_qualified(qualified_name, None)
        return Instance(cast(TypeInfo, sym.node), [])

    def is_instance_type(self, t: Type) -> bool:
        return isinstance(t, Instance)

    def add_class_type_variables_to_symbol_table(
            self, info: TypeInfo) -> List[SymbolTableNode]:
        vars = info.type_vars
        nodes = List[SymbolTableNode]()
        if vars:
            for i in range(len(vars)):
                node = self.add_type_var(vars[i], i + 1, info)
                nodes.append(node)
        return nodes

    def visit_import(self, i: Import) -> None:
        for id, as_id in i.ids:
            if as_id != id:
                self.add_module_symbol(id, as_id, i)
            else:
                base = id.split('.')[0]
                self.add_module_symbol(base, base, i)

    def add_module_symbol(self, id: str, as_id: str, context: Context) -> None:
        if id in self.modules:
            m = self.modules[id]
            self.add_symbol(as_id, SymbolTableNode(MODULE_REF, m, self.cur_mod_id), context)
        else:
            self.add_unknown_symbol(as_id, context)

    def visit_import_from(self, i: ImportFrom) -> None:
        if i.id in self.modules:
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
        else:
            for id, as_id in i.names:
                self.add_unknown_symbol(as_id, i)

    def normalize_type_alias(self, node: SymbolTableNode,
                             ctx: Context) -> SymbolTableNode:
        if node.fullname in type_aliases:
            # Node refers to an aliased type such as typing.List; normalize.
            node = self.lookup_qualified(type_aliases[node.fullname], ctx)
        return node

    def visit_import_all(self, i: ImportAll) -> None:
        if i.id in self.modules:
            m = self.modules[i.id]
            for name, node in m.names.items():
                node = self.normalize_type_alias(node, i)
                if not name.startswith('_'):
                    self.add_symbol(name, SymbolTableNode(node.kind, node.node,
                                                          self.cur_mod_id), i)
        else:
            # Don't add any dummy symbols for 'from x import *' if 'x' is unknown.
            pass

    def add_unknown_symbol(self, name: str, context: Context) -> None:
        var = Var(name)
        var._fullname = self.qualified_name(name)
        var.is_ready = True
        var.type = AnyType()
        self.add_symbol(name, SymbolTableNode(GDEF, var, self.cur_mod_id), context)

    #
    # Statements
    #

    def visit_block(self, b: Block) -> None:
        if b.is_unreachable:
            return
        self.block_depth[-1] += 1
        for s in b.body:
            s.accept(self)
        self.block_depth[-1] -= 1

    def visit_block_maybe(self, b: Block) -> None:
        if b:
            self.visit_block(b)

    def visit_var_def(self, defn: VarDef) -> None:
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

    def anal_type(self, t: Type) -> Type:
        if t:
            a = TypeAnalyser(self.lookup_qualified,
                             self.lookup_fully_qualified,
                             self.stored_vars, self.fail)
            return t.accept(a)
        else:
            return None

    def visit_assignment_stmt(self, s: AssignmentStmt) -> None:
        for lval in s.lvalues:
            self.analyse_lvalue(lval, explicit_type=s.type is not None)
        s.rvalue.accept(self)
        if s.type:
            s.type = self.anal_type(s.type)
        else:
            s.type = self.infer_type_from_undefined(s.rvalue)
            # For simple assignments, allow binding type aliases
            if (s.type is None and len(s.lvalues) == 1 and
                    isinstance(s.lvalues[0], NameExpr)):
                res = analyse_node(self.lookup_qualified, s.rvalue, s)
                if res:
                    # XXX Need to remove this later if reassigned
                    x = cast(NameExpr, s.lvalues[0])
                    self.stored_vars[x.node] = res

        if s.type:
            # Store type into nodes.
            for lvalue in s.lvalues:
                self.store_declared_types(lvalue, s.type)
        self.check_and_set_up_type_alias(s)
        self.process_typevar_declaration(s)

    def check_and_set_up_type_alias(self, s: AssignmentStmt) -> None:
        """Check if assignment creates a type alias and set it up as needed."""
        # For now, type aliases only work at the top level of a module.
        if (len(s.lvalues) == 1 and not self.is_func_scope() and not self.type
                and not s.type):
            lvalue = s.lvalues[0]
            if isinstance(lvalue, NameExpr):
                if not lvalue.is_def:
                    # Only a definition can create a type alias, not regular assignment.
                    return
                rvalue = s.rvalue
                if isinstance(rvalue, RefExpr):
                    node = rvalue.node
                    if isinstance(node, TypeInfo):
                        # TODO: We should record the fact that this is a variable
                        #       that refers to a type, rather than making this
                        #       just an alias for the type.
                        self.globals[lvalue.name].node = node

    def analyse_lvalue(self, lval: Node, nested: bool = False,
                       add_global: bool = False,
                       explicit_type: bool = False) -> None:
        """Analyze an lvalue or assignment target.

        Only if add_global is True, add name to globals table. If nested
        is true, the lvalue is within a tuple or list lvalue expression.
        """

        if isinstance(lval, NameExpr):
            nested_global = (not self.is_func_scope() and
                             self.block_depth[-1] > 0 and
                             not self.type)
            if (add_global or nested_global) and lval.name not in self.globals:
                # Define new global name.
                v = Var(lval.name)
                v._fullname = self.qualified_name(lval.name)
                v.is_ready = False  # Type not inferred yet
                lval.node = v
                lval.is_def = True
                lval.kind = GDEF
                lval.fullname = v._fullname
                self.globals[lval.name] = SymbolTableNode(GDEF, v,
                                                          self.cur_mod_id)
            elif isinstance(lval.node, Var) and lval.is_def:
                # Since the is_def flag is set, this must have been analyzed
                # already in the first pass and added to the symbol table.
                v = cast(Var, lval.node)
                assert v.name() in self.globals
            elif (self.is_func_scope() and lval.name not in self.locals[-1] and
                  lval.name not in self.global_decls[-1]):
                # Define new local name.
                v = Var(lval.name)
                lval.node = v
                lval.is_def = True
                lval.kind = LDEF
                lval.fullname = lval.name
                self.add_local(v, lval)
            elif not self.is_func_scope() and (self.type and
                                               lval.name not in self.type.names):
                # Define a new attribute within class body.
                v = Var(lval.name)
                v.info = self.type
                v.is_initialized_in_class = True
                lval.node = v
                lval.is_def = True
                lval.kind = MDEF
                lval.fullname = lval.name
                self.type.names[lval.name] = SymbolTableNode(MDEF, v)
            else:
                # Bind to an existing name.
                if explicit_type:
                    self.name_already_defined(lval.name, lval)
                lval.accept(self)
                self.check_lvalue_validity(lval.node, lval)
        elif isinstance(lval, MemberExpr):
            if not add_global:
                self.analyse_member_lvalue(lval)
            if explicit_type and not self.is_self_member_ref(lval):
                self.fail('Type cannot be declared in assignment to non-self '
                          'attribute', lval)
        elif isinstance(lval, IndexExpr):
            if explicit_type:
                self.fail('Unexpected type declaration', lval)
            if not add_global:
                lval.accept(self)
        elif isinstance(lval, ParenExpr):
            self.analyse_lvalue(lval.expr, nested, add_global, explicit_type)
        elif (isinstance(lval, TupleExpr) or
              isinstance(lval, ListExpr)):
            items = (Any(lval)).items
            if len(items) == 0 and isinstance(lval, TupleExpr):
                self.fail("Can't assign to ()", lval)
            for i in items:
                self.analyse_lvalue(i, nested=True, add_global=add_global,
                                    explicit_type = explicit_type)
        else:
            self.fail('Invalid assignment target', lval)

    def analyse_member_lvalue(self, lval: MemberExpr) -> None:
        lval.accept(self)
        if (self.is_self_member_ref(lval) and
                self.type.get(lval.name) is None):
            # Implicit attribute definition in __init__.
            lval.is_def = True
            v = Var(lval.name)
            v.info = self.type
            v.is_ready = False
            lval.def_var = v
            lval.node = v
            self.type.names[lval.name] = SymbolTableNode(MDEF, v)
        self.check_lvalue_validity(lval.node, lval)

    def is_self_member_ref(self, memberexpr: MemberExpr) -> bool:
        """Does memberexpr to refer to an attribute of self?"""
        if not isinstance(memberexpr.expr, NameExpr):
            return False
        node = (cast(NameExpr, memberexpr.expr)).node
        return isinstance(node, Var) and (cast(Var, node)).is_self

    def check_lvalue_validity(self, node: Node, ctx: Context) -> None:
        if isinstance(node, (FuncDef, TypeInfo, TypeVarExpr)):
            self.fail('Invalid assignment target', ctx)

    def infer_type_from_undefined(self, rvalue: Node) -> Type:
        if isinstance(rvalue, CallExpr):
            if isinstance(rvalue.analyzed, UndefinedExpr):
                undef = cast(UndefinedExpr, rvalue.analyzed)
                return undef.type
        return None

    def store_declared_types(self, lvalue: Node, typ: Type) -> None:
        if isinstance(lvalue, RefExpr):
            lvalue.is_def = False
            if isinstance(lvalue.node, Var):
                var = cast(Var, lvalue.node)
                var.type = typ
                var.is_ready = True
            # If node is not a variable, we'll catch it elsewhere.
        elif isinstance(lvalue, TupleExpr):
            if isinstance(typ, TupleType):
                if len(lvalue.items) != len(typ.items):
                    self.fail('Incompatible number of tuple items', lvalue)
                    return
                for item, itemtype in zip(lvalue.items, typ.items):
                    self.store_declared_types(item, itemtype)
            else:
                self.fail('Tuple type expected for multiple variables',
                          lvalue)
        elif isinstance(lvalue, ParenExpr):
            self.store_declared_types(lvalue.expr, typ)
        else:
            raise RuntimeError('Internal error (%s)' % type(lvalue))

    def process_typevar_declaration(self, s: AssignmentStmt) -> None:
        """Check if s declares a typevar; it yes, store it in symbol table."""
        if len(s.lvalues) != 1 or not isinstance(s.lvalues[0], NameExpr):
            return
        if not isinstance(s.rvalue, CallExpr):
            return
        call = cast(CallExpr, s.rvalue)
        if not isinstance(call.callee, RefExpr):
            return
        callee = cast(RefExpr, call.callee)
        if callee.fullname != 'typing.typevar':
            return
        # TODO Share code with check_argument_count in checkexpr.py?
        if len(call.args) < 1:
            self.fail("Too few arguments for typevar()", s)
            return
        if len(call.args) > 2:
            self.fail("Too many arguments for typevar()", s)
            return
        if call.arg_kinds not in ([ARG_POS], [ARG_POS, ARG_NAMED]):
            self.fail("Unexpected arguments to typevar()", s)
            return
        if not isinstance(call.args[0], StrExpr):
            self.fail("typevar() expects a string literal argument", s)
            return
        lvalue = cast(NameExpr, s.lvalues[0])
        name = lvalue.name
        if cast(StrExpr, call.args[0]).value != name:
            self.fail("Unexpected typevar() argument value", s)
            return
        if not lvalue.is_def:
            if s.type:
                self.fail("Cannot declare the type of a type variable", s)
            else:
                self.fail("Cannot redefine '%s' as a type variable" % name, s)
            return
        if len(call.args) == 2:
            # Analyze values=(...) argument.
            if call.arg_names[1] != 'values':
                self.fail("Unexpected keyword argument '{}' to typevar()".
                          format(call.arg_names[1]), s)
                return
            if isinstance(call.args[1], ParenExpr):
                expr = cast(ParenExpr, call.args[1]).expr
                if isinstance(expr, TupleExpr):
                    values = self.analyze_types(expr.items)
                else:
                    self.fail('The values argument must be a tuple literal', s)
                    return
            else:
                self.fail('The values argument must be in parentheses (...)',
                          s)
                return
        else:
            values = []
        # Yes, it's a valid type variable definition!
        node = self.lookup(name, s)
        node.kind = UNBOUND_TVAR
        typevar = TypeVarExpr(name, node.fullname, values)
        typevar.line = call.line
        call.analyzed = typevar
        node.node = typevar

    def analyze_types(self, items: List[Node]) -> List[Type]:
        result = List[Type]()
        for node in items:
            try:
                result.append(self.anal_type(expr_to_unanalyzed_type(node)))
            except TypeTranslationError:
                self.fail('Type expected', node)
                result.append(AnyType())
        return result

    def visit_decorator(self, dec: Decorator) -> None:
        if not dec.is_overload:
            if self.is_func_scope():
                self.add_symbol(dec.var.name(), SymbolTableNode(LDEF, dec),
                                dec)
            elif self.type:
                dec.var.info = self.type
                dec.var.is_initialized_in_class = True
                self.add_symbol(dec.var.name(), SymbolTableNode(MDEF, dec),
                                dec)
        for d in dec.decorators:
            d.accept(self)
        removed = List[int]()
        for i, d in enumerate(dec.decorators):
            if refers_to_fullname(d, 'abc.abstractmethod'):
                removed.append(i)
                dec.func.is_abstract = True
                self.check_decorated_function_is_method('abstractmethod', dec)
            elif refers_to_fullname(d, 'builtins.staticmethod'):
                removed.append(i)
                dec.func.is_static = True
                dec.var.is_staticmethod = True
                self.check_decorated_function_is_method('staticmethod', dec)
            elif refers_to_fullname(d, 'builtins.classmethod'):
                removed.append(i)
                dec.func.is_class = True
                dec.var.is_classmethod = True
                self.check_decorated_function_is_method('classmethod', dec)
            elif refers_to_fullname(d, 'builtins.property'):
                removed.append(i)
                dec.func.is_property = True
                dec.var.is_property = True
                if dec.is_overload:
                    self.fail('A property cannot be overloaded', dec)
                self.check_decorated_function_is_method('property', dec)
                if len(dec.func.args) > 1:
                    self.fail('Too many arguments', dec.func)
        for i in reversed(removed):
            del dec.decorators[i]
        dec.func.accept(self)
        if not dec.decorators and not dec.var.is_property:
            # No non-special decorators left. We can trivially infer the type
            # of the function here.
            dec.var.type = dec.func.type

    def check_decorated_function_is_method(self, decorator: str,
                                           context: Context) -> None:
        if not self.type or self.is_func_scope():
            self.fail("'%s' used with a non-method" % decorator, context)

    def visit_expression_stmt(self, s: ExpressionStmt) -> None:
        s.expr.accept(self)

    def visit_return_stmt(self, s: ReturnStmt) -> None:
        if not self.is_func_scope():
            self.fail("'return' outside function", s)
        if s.expr:
            s.expr.accept(self)

    def visit_raise_stmt(self, s: RaiseStmt) -> None:
        if s.expr:
            s.expr.accept(self)
        if s.from_expr:
            s.from_expr.accept(self)

    def visit_yield_stmt(self, s: YieldStmt) -> None:
        if not self.is_func_scope():
            self.fail("'yield' outside function", s)
        else:
            self.function_stack[-1].is_generator = True
        if s.expr:
            s.expr.accept(self)

    def visit_assert_stmt(self, s: AssertStmt) -> None:
        if s.expr:
            s.expr.accept(self)

    def visit_operator_assignment_stmt(self,
                                       s: OperatorAssignmentStmt) -> None:
        s.lvalue.accept(self)
        s.rvalue.accept(self)

    def visit_while_stmt(self, s: WhileStmt) -> None:
        s.expr.accept(self)
        self.loop_depth += 1
        s.body.accept(self)
        self.loop_depth -= 1
        self.visit_block_maybe(s.else_body)

    def visit_for_stmt(self, s: ForStmt) -> None:
        s.expr.accept(self)

        # Bind index variables and check if they define new names.
        for n in s.index:
            self.analyse_lvalue(n)

        self.loop_depth += 1
        self.visit_block(s.body)
        self.loop_depth -= 1

        self.visit_block_maybe(s.else_body)

    def visit_break_stmt(self, s: BreakStmt) -> None:
        if self.loop_depth == 0:
            self.fail("'break' outside loop", s)

    def visit_continue_stmt(self, s: ContinueStmt) -> None:
        if self.loop_depth == 0:
            self.fail("'continue' outside loop", s)

    def visit_if_stmt(self, s: IfStmt) -> None:
        infer_reachability_of_if_statement(s, pyversion=self.pyversion)
        for i in range(len(s.expr)):
            s.expr[i].accept(self)
            self.visit_block(s.body[i])
        self.visit_block_maybe(s.else_body)

    def visit_try_stmt(self, s: TryStmt) -> None:
        self.analyze_try_stmt(s, self)

    def analyze_try_stmt(self, s: TryStmt, visitor: NodeVisitor,
                         add_global: bool = False) -> None:
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

    def visit_with_stmt(self, s: WithStmt) -> None:
        for e in s.expr:
            e.accept(self)
        for n in s.name:
            if n:
                self.analyse_lvalue(n)
        self.visit_block(s.body)

    def visit_del_stmt(self, s: DelStmt) -> None:
        s.expr.accept(self)
        if not isinstance(s.expr, (IndexExpr, NameExpr, MemberExpr)):
            self.fail('Invalid delete target', s)

    def visit_global_decl(self, g: GlobalDecl) -> None:
        for n in g.names:
            self.global_decls[-1].add(n)

    def visit_print_stmt(self, s: PrintStmt) -> None:
        for arg in s.args:
            arg.accept(self)

    #
    # Expressions
    #

    def visit_name_expr(self, expr: NameExpr) -> None:
        n = self.lookup(expr.name, expr)
        if n:
            if n.kind == TVAR:
                self.fail("'{}' is a type variable and only valid in type "
                          "context".format(expr.name), expr)
            else:
                expr.kind = n.kind
                expr.node = (cast(Node, n.node))
                expr.fullname = n.fullname

    def visit_super_expr(self, expr: SuperExpr) -> None:
        if not self.type:
            self.fail('"super" used outside class', expr)
            return
        expr.info = self.type

    def visit_tuple_expr(self, expr: TupleExpr) -> None:
        for item in expr.items:
            item.accept(self)

    def visit_list_expr(self, expr: ListExpr) -> None:
        for item in expr.items:
            item.accept(self)

    def visit_set_expr(self, expr: SetExpr) -> None:
        for item in expr.items:
            item.accept(self)

    def visit_dict_expr(self, expr: DictExpr) -> None:
        for key, value in expr.items:
            key.accept(self)
            value.accept(self)

    def visit_paren_expr(self, expr: ParenExpr) -> None:
        expr.expr.accept(self)

    def visit_call_expr(self, expr: CallExpr) -> None:
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
            expr.analyzed = CastExpr(expr.args[0], AnyType())
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
        elif refers_to_fullname(expr.callee, 'typing.ducktype'):
            # Special form ducktype(...).
            if not self.check_fixed_args(expr, 1, 'ducktype'):
                return
            # Translate first argument to an unanalyzed type.
            try:
                target = expr_to_unanalyzed_type(expr.args[0])
            except TypeTranslationError:
                self.fail('Argument 1 to ducktype is not a type', expr)
                return
            expr.analyzed = DucktypeExpr(target)
            expr.analyzed.line = expr.line
            expr.analyzed.accept(self)
        elif refers_to_fullname(expr.callee, 'typing.disjointclass'):
            # Special form disjointclass(...).
            if not self.check_fixed_args(expr, 1, 'disjointclass'):
                return
            arg = expr.args[0]
            if isinstance(arg, RefExpr):
                expr.analyzed = DisjointclassExpr(arg)
                expr.analyzed.line = expr.line
                expr.analyzed.accept(self)
            else:
                self.fail('Argument 1 to disjointclass is not a class', expr)
        else:
            # Normal call expression.
            for a in expr.args:
                a.accept(self)

    def check_fixed_args(self, expr: CallExpr, numargs: int,
                         name: str) -> bool:
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

    def visit_member_expr(self, expr: MemberExpr) -> None:
        base = expr.expr
        base.accept(self)
        # Bind references to module attributes.
        if isinstance(base, RefExpr) and cast(RefExpr,
                                              base).kind == MODULE_REF:
            names = (cast(MypyFile, (cast(RefExpr, base)).node)).names
            n = names.get(expr.name, None)
            if n:
                n = self.normalize_type_alias(n, expr)
                if not n:
                    return
                expr.kind = n.kind
                expr.fullname = n.fullname
                expr.node = n.node

    def visit_op_expr(self, expr: OpExpr) -> None:
        expr.left.accept(self)
        expr.right.accept(self)

    def visit_comparison_expr(self, expr: ComparisonExpr) -> None:
        for operand in expr.operands:
            operand.accept(self)

    def visit_unary_expr(self, expr: UnaryExpr) -> None:
        expr.expr.accept(self)

    def visit_index_expr(self, expr: IndexExpr) -> None:
        expr.base.accept(self)
        if refers_to_class_or_function(expr.base):
            # Special form -- type application.
            # Translate index to an unanalyzed type.
            types = List[Type]()
            if isinstance(expr.index, TupleExpr):
                items = (cast(TupleExpr, expr.index)).items
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

    def visit_slice_expr(self, expr: SliceExpr) -> None:
        if expr.begin_index:
            expr.begin_index.accept(self)
        if expr.end_index:
            expr.end_index.accept(self)
        if expr.stride:
            expr.stride.accept(self)

    def visit_cast_expr(self, expr: CastExpr) -> None:
        expr.expr.accept(self)
        expr.type = self.anal_type(expr.type)

    def visit_undefined_expr(self, expr: UndefinedExpr) -> None:
        expr.type = self.anal_type(expr.type)

    def visit_type_application(self, expr: TypeApplication) -> None:
        expr.expr.accept(self)
        for i in range(len(expr.types)):
            expr.types[i] = self.anal_type(expr.types[i])

    def visit_list_comprehension(self, expr: ListComprehension) -> None:
        expr.generator.accept(self)

    def visit_generator_expr(self, expr: GeneratorExpr) -> None:
        self.enter()

        for index, sequence, conditions in zip(expr.indices, expr.sequences,
                                               expr.condlists):
            sequence.accept(self)
            # Bind index variables.
            for n in index:
                self.analyse_lvalue(n)
            for cond in conditions:
                cond.accept(self)

        expr.left_expr.accept(self)
        self.leave()

    def visit_func_expr(self, expr: FuncExpr) -> None:
        self.analyse_function(expr)

    def visit_conditional_expr(self, expr: ConditionalExpr) -> None:
        expr.if_expr.accept(self)
        expr.cond.accept(self)
        expr.else_expr.accept(self)

    def visit_ducktype_expr(self, expr: DucktypeExpr) -> None:
        expr.type = self.anal_type(expr.type)

    def visit_disjointclass_expr(self, expr: DisjointclassExpr) -> None:
        expr.cls.accept(self)

    #
    # Helpers
    #

    def lookup(self, name: str, ctx: Context) -> SymbolTableNode:
        """Look up an unqualified name in all active namespaces."""
        # 1. Name declared using 'global x' takes precedence
        if name in self.global_decls[-1]:
            if name in self.globals:
                return self.globals[name]
            else:
                self.name_not_defined(name, ctx)
                return None
        # 2. Class attributes (if within class definition)
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
            table = cast(MypyFile, b.node).names
            if name in table:
                if name[0] == "_" and name[1] != "_":
                    self.name_not_defined(name, ctx)
                    return None
                node = table[name]
                # Only succeed if we are not using a type alias such List -- these must be
                # be accessed via the typing module.
                if node.node.name() == name:
                    return node
        # Give up.
        self.name_not_defined(name, ctx)
        return None

    def lookup_qualified(self, name: str, ctx: Context) -> SymbolTableNode:
        if '.' not in name:
            return self.lookup(name, ctx)
        else:
            parts = name.split('.')
            n = self.lookup(parts[0], ctx)  # type: SymbolTableNode
            if n:
                for i in range(1, len(parts)):
                    if isinstance(n.node, TypeInfo):
                        n = cast(TypeInfo, n.node).get(parts[i])
                    elif isinstance(n.node, MypyFile):
                        n = cast(MypyFile, n.node).names.get(parts[i], None)
                    if not n:
                        self.name_not_defined(name, ctx)
                        break
                if n:
                    n = self.normalize_type_alias(n, ctx)
            return n

    def builtin_type(self, fully_qualified_name: str) -> Instance:
        node = self.lookup_fully_qualified(fully_qualified_name)
        info = cast(TypeInfo, node.node)
        return Instance(info, [])

    def lookup_fully_qualified(self, name: str) -> SymbolTableNode:
        """Lookup a fully qualified name.

        Assume that the name is defined. This happens in the global namespace -- the local
        module namespace is ignored.
        """
        assert '.' in name
        parts = name.split('.')
        n = self.modules[parts[0]]
        for i in range(1, len(parts) - 1):
            n = cast(MypyFile, n.names[parts[i]].node)
        return n.names[parts[-1]]

    def qualified_name(self, n: str) -> str:
        return self.cur_mod_id + '.' + n

    def enter(self) -> None:
        self.locals.append(SymbolTable())
        self.global_decls.append(set())

    def leave(self) -> None:
        self.locals.pop()
        self.global_decls.pop()

    def is_func_scope(self) -> bool:
        return self.locals[-1] is not None

    def is_class_scope(self) -> bool:
        return self.type is not None and not self.is_func_scope()

    def add_symbol(self, name: str, node: SymbolTableNode,
                   context: Context) -> None:
        if self.is_func_scope():
            if name in self.locals[-1]:
                # Flag redefinition unless this is a reimport of a module.
                if not (node.kind == MODULE_REF and
                        self.locals[-1][name].node == node.node):
                    self.name_already_defined(name, context)
            self.locals[-1][name] = node
        elif self.type:
            self.type.names[name] = node
        else:
            if name in self.globals and (not isinstance(node.node, MypyFile) or
                                         self.globals[name].node != node.node):
                # Modules can be imported multiple times to support import
                # of multiple submodules of a package (e.g. a.x and a.y).
                self.name_already_defined(name, context)
            self.globals[name] = node

    def add_var(self, v: Var, ctx: Context) -> None:
        if self.is_func_scope():
            self.add_local(v, ctx)
        else:
            self.globals[v.name()] = SymbolTableNode(GDEF, v, self.cur_mod_id)
            v._fullname = self.qualified_name(v.name())

    def add_local(self, v: Var, ctx: Context) -> None:
        if v.name() in self.locals[-1]:
            self.name_already_defined(v.name(), ctx)
        v._fullname = v.name()
        self.locals[-1][v.name()] = SymbolTableNode(LDEF, v)

    def add_local_func(self, defn: FuncBase, ctx: Context) -> None:
        # TODO combine with above
        if defn.name() in self.locals[-1]:
            self.name_already_defined(defn.name(), ctx)
        self.locals[-1][defn.name()] = SymbolTableNode(LDEF, defn)

    def check_no_global(self, n: str, ctx: Context,
                        is_func: bool = False) -> None:
        if n in self.globals:
            if is_func and isinstance(self.globals[n].node, FuncDef):
                self.fail(("Name '{}' already defined (overload variants "
                           "must be next to each other)").format(n), ctx)
            else:
                self.name_already_defined(n, ctx)

    def name_not_defined(self, name: str, ctx: Context) -> None:
        self.fail("Name '{}' is not defined".format(name), ctx)

    def name_already_defined(self, name: str, ctx: Context) -> None:
        self.fail("Name '{}' already defined".format(name), ctx)

    def fail(self, msg: str, ctx: Context) -> None:
        self.errors.report(ctx.get_line(), msg)


class FirstPass(NodeVisitor):
    """First phase of semantic analysis"""

    def __init__(self, sem: SemanticAnalyzer) -> None:
        self.sem = sem
        self.pyversion = sem.pyversion

    def analyze(self, file: MypyFile, fnam: str, mod_id: str) -> None:
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
            name_def = VarDef([Var(n, AnyType())], True)
            defs.insert(0, name_def)

        for d in defs:
            d.accept(self)

        # Add implicit definition of 'None' to builtins, as we cannot define a
        # variable with a None type explicitly.
        if mod_id == 'builtins':
            none_def = VarDef([Var('None', NoneTyp())], True)
            defs.append(none_def)
            none_def.accept(self)

    def visit_block(self, b: Block) -> None:
        if b.is_unreachable:
            return
        self.sem.block_depth[-1] += 1
        for node in b.body:
            node.accept(self)
        self.sem.block_depth[-1] -= 1

    def visit_assignment_stmt(self, s: AssignmentStmt) -> None:
        for lval in s.lvalues:
            self.sem.analyse_lvalue(lval, add_global=True,
                                    explicit_type=s.type is not None)

    def visit_func_def(self, d: FuncDef) -> None:
        sem = self.sem
        d.is_conditional = sem.block_depth[-1] > 0
        if d.name() in sem.globals:
            n = sem.globals[d.name()].node
            if sem.is_conditional_func(n, d):
                # Conditional function definition -- multiple defs are ok.
                d.original_def = cast(FuncDef, n)
            else:
                sem.check_no_global(d.name(), d, True)
        d._fullname = sem.qualified_name(d.name())
        sem.globals[d.name()] = SymbolTableNode(GDEF, d, sem.cur_mod_id)

    def visit_overloaded_func_def(self, d: OverloadedFuncDef) -> None:
        self.sem.check_no_global(d.name(), d)
        d._fullname = self.sem.qualified_name(d.name())
        self.sem.globals[d.name()] = SymbolTableNode(GDEF, d,
                                                     self.sem.cur_mod_id)

    def visit_class_def(self, d: ClassDef) -> None:
        self.sem.check_no_global(d.name, d)
        d.fullname = self.sem.qualified_name(d.name)
        info = TypeInfo(SymbolTable(), d)
        info.set_line(d.line)
        d.info = info
        self.sem.globals[d.name] = SymbolTableNode(GDEF, info,
                                                   self.sem.cur_mod_id)

    def visit_var_def(self, d: VarDef) -> None:
        for v in d.items:
            self.sem.check_no_global(v.name(), d)
            v._fullname = self.sem.qualified_name(v.name())
            self.sem.globals[v.name()] = SymbolTableNode(GDEF, v,
                                                         self.sem.cur_mod_id)

    def visit_for_stmt(self, s: ForStmt) -> None:
        for n in s.index:
            self.sem.analyse_lvalue(n, add_global=True)

    def visit_with_stmt(self, s: WithStmt) -> None:
        for n in s.name:
            if n:
                self.sem.analyse_lvalue(n, add_global=True)

    def visit_decorator(self, d: Decorator) -> None:
        d.var._fullname = self.sem.qualified_name(d.var.name())
        self.sem.add_symbol(d.var.name(), SymbolTableNode(GDEF, d.var), d)

    def visit_if_stmt(self, s: IfStmt) -> None:
        infer_reachability_of_if_statement(s, pyversion=self.pyversion)
        for node in s.body:
            node.accept(self)
        if s.else_body:
            s.else_body.accept(self)

    def visit_try_stmt(self, s: TryStmt) -> None:
        self.sem.analyze_try_stmt(s, self, add_global=True)


class ThirdPass(TraverserVisitor[None]):
    """The third and final pass of semantic analysis.

    Check type argument counts and values of generic types. Also update
    TypeInfo disjointclass information.
    """

    def __init__(self, errors: Errors) -> None:
        self.errors = errors

    def visit_file(self, file_node: MypyFile, fnam: str) -> None:
        self.errors.set_file(fnam)
        file_node.accept(self)

    def visit_func_def(self, fdef: FuncDef) -> None:
        self.errors.push_function(fdef.name())
        self.analyze(fdef.type)
        super().visit_func_def(fdef)
        self.errors.pop_function()

    def visit_class_def(self, tdef: ClassDef) -> None:
        for type in tdef.info.bases:
            self.analyze(type)
        info = tdef.info
        # Collect declared disjoint classes from all base classes.
        for base in info.mro:
            for disjoint in base.disjoint_classes:
                if disjoint not in info.disjoint_classes:
                    info.disjoint_classes.append(disjoint)
                    for subtype in disjoint.all_subtypes():
                        if info not in subtype.disjoint_classes:
                            subtype.disjoint_classes.append(info)
        super().visit_class_def(tdef)

    def visit_assignment_stmt(self, s: AssignmentStmt) -> None:
        self.analyze(s.type)
        super().visit_assignment_stmt(s)

    def visit_undefined_expr(self, e: UndefinedExpr) -> None:
        self.analyze(e.type)

    def visit_cast_expr(self, e: CastExpr) -> None:
        self.analyze(e.type)
        super().visit_cast_expr(e)

    def visit_type_application(self, e: TypeApplication) -> None:
        for type in e.types:
            self.analyze(type)
        super().visit_type_application(e)

    def analyze(self, type: Type) -> None:
        if type:
            analyzer = TypeAnalyserPass3(self.fail)
            type.accept(analyzer)

    def fail(self, msg: str, ctx: Context) -> None:
        self.errors.report(ctx.get_line(), msg)


def self_type(typ: TypeInfo) -> Instance:
    """For a non-generic type, return instance type representing the type.
    For a generic G type with parameters T1, .., Tn, return G[T1, ..., Tn].
    """
    tv = List[Type]()
    for i in range(len(typ.type_vars)):
        tv.append(TypeVar(typ.type_vars[i], i + 1,
                          typ.defn.type_vars[i].values,
                          typ.defn.type_vars[i].upper_bound))
    return Instance(typ, tv)


@overload
def replace_implicit_first_type(sig: Callable, new: Type) -> Callable:
    # We can detect implicit self type by it having no representation.
    if not sig.arg_types[0].repr:
        return replace_leading_arg_type(sig, new)
    else:
        return sig


@overload
def replace_implicit_first_type(sig: FunctionLike, new: Type) -> FunctionLike:
    osig = cast(Overloaded, sig)
    return Overloaded([replace_implicit_first_type(i, new)
                       for i in osig.items()])


def set_callable_name(sig: Type, fdef: FuncDef) -> Type:
    if isinstance(sig, FunctionLike):
        if fdef.info:
            return sig.with_name(
                '"{}" of "{}"'.format(fdef.name(), fdef.info.name()))
        else:
            return sig.with_name('"{}"'.format(fdef.name()))
    else:
        return sig


def refers_to_fullname(node: Node, fullname: str) -> bool:
    """Is node a name or member expression with the given full name?"""
    return isinstance(node,
                      RefExpr) and cast(RefExpr, node).fullname == fullname


def refers_to_class_or_function(node: Node) -> bool:
    """Does semantically analyzed node refer to a class?"""
    return (isinstance(node, RefExpr) and
            isinstance(cast(RefExpr, node).node, (TypeInfo, FuncDef,
                                                  OverloadedFuncDef)))


def expr_to_unanalyzed_type(expr: Node) -> Type:
    """Translate an expression to the corresonding type.

    The result is not semantically analyzed. It can be UnboundType or ListType.
    Raise TypeTranslationError if the expression cannot represent a type.
    """
    if isinstance(expr, NameExpr):
        name = expr.name
        return UnboundType(name, line=expr.line)
    elif isinstance(expr, MemberExpr):
        fullname = get_member_expr_fullname(expr)
        if fullname:
            return UnboundType(fullname, line=expr.line)
        else:
            raise TypeTranslationError()
    elif isinstance(expr, IndexExpr):
        base = expr_to_unanalyzed_type(expr.base)
        if isinstance(base, UnboundType):
            if base.args:
                raise TypeTranslationError()
            if isinstance(expr.index, TupleExpr):
                args = cast(TupleExpr, expr.index).items
            else:
                args = [expr.index]
            base.args = [expr_to_unanalyzed_type(arg) for arg in args]
            return base
        else:
            raise TypeTranslationError()
    elif isinstance(expr, ListExpr):
        return TypeList([expr_to_unanalyzed_type(t) for t in expr.items],
                        line=expr.line)
    elif isinstance(expr, StrExpr):
        # Parse string literal type.
        try:
            result = parse_str_as_type(expr.value, expr.line)
        except TypeParseError:
            raise TypeTranslationError()
        return result
    else:
        raise TypeTranslationError()


def get_member_expr_fullname(expr: MemberExpr) -> str:
    """Return the qualified name represention of a member expression.

    Return a string of form foo.bar, foo.bar.baz, or similar, or None if the
    argument cannot be represented in this form.
    """
    if isinstance(expr.expr, NameExpr):
        initial = cast(NameExpr, expr.expr).name
    elif isinstance(expr.expr, MemberExpr):
        initial = get_member_expr_fullname(cast(MemberExpr, expr.expr))
    else:
        return None
    return '{}.{}'.format(initial, expr.name)


def find_duplicate(list: List[T]) -> T:
    """If the list has duplicates, return one of the duplicates.

    Otherwise, return None.
    """
    for i in range(1, len(list)):
        if list[i] in list[:i]:
            return list[i]
    return None


def disable_typevars(nodes: List[SymbolTableNode]) -> None:
    for node in nodes:
        assert node.kind in (TVAR, UNBOUND_TVAR)
        node.kind = UNBOUND_TVAR


def enable_typevars(nodes: List[SymbolTableNode]) -> None:
    for node in nodes:
        assert node.kind in (TVAR, UNBOUND_TVAR)
        node.kind = TVAR


def remove_imported_names_from_symtable(names: SymbolTable,
                                        module: str) -> None:
    """Remove all imported names from the symbol table of a module."""
    removed = List[str]()
    for name, node in names.items():
        fullname = node.node.fullname()
        prefix = fullname[:fullname.rfind('.')]
        if prefix != module:
            removed.append(name)
    for name in removed:
        del names[name]


def infer_reachability_of_if_statement(s: IfStmt, pyversion: int) -> None:
    always_true = False
    for i in range(len(s.expr)):
        result = infer_if_condition_value(s.expr[i], pyversion)
        if result == ALWAYS_FALSE:
            # The condition is always false, so we skip the if/elif body.
            mark_block_unreachable(s.body[i])
        elif result == ALWAYS_TRUE:
            # This condition is always true, so all of the remaining
            # elif/else bodies will never be executed.
            always_true = True
            for body in s.body[i + 1:]:
                mark_block_unreachable(s.body[i])
            if s.else_body:
                mark_block_unreachable(s.else_body)
            break


def infer_if_condition_value(expr: Node, pyversion: int) -> int:
    """Infer whether if condition is always true/false.

    Return ALWAYS_TRUE if always true, ALWAYS_FALSE if always false,
    and TRUTH_VALUE_UNKNOWN otherwise.
    """
    name = ''
    negated = False
    alias = expr
    if isinstance(alias, UnaryExpr):
        if alias.op == 'not':
            expr = alias.expr
            negated = True
    if isinstance(expr, NameExpr):
        name = expr.name
    elif isinstance(expr, MemberExpr):
        name = expr.name
    result = TRUTH_VALUE_UNKNOWN
    if name == 'PY2':
        result = ALWAYS_TRUE if pyversion == 2 else ALWAYS_FALSE
    elif name == 'PY3':
        result = ALWAYS_TRUE if pyversion == 3 else ALWAYS_FALSE
    elif name == 'MYPY':
        result = ALWAYS_TRUE
    if negated:
        if result == ALWAYS_TRUE:
            result = ALWAYS_FALSE
        elif result == ALWAYS_FALSE:
            result = ALWAYS_TRUE
    return result


def mark_block_unreachable(block: Block) -> None:
    block.is_unreachable = True
    block.accept(MarkImportsUnreachableVisitor())


class MarkImportsUnreachableVisitor(TraverserVisitor):
    """Visitor that flags all imports nested within a node as unreachable."""

    def visit_import(self, node: Import) -> None:
        node.is_unreachable = True

    def visit_import_from(self, node: ImportFrom) -> None:
        node.is_unreachable = True

    def visit_import_all(self, node: ImportAll) -> None:
        node.is_unreachable = True
