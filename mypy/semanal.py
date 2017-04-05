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
   file, which would not have the type argument count set yet. This
   pass also recomputes the method resolution order of each class, in
   case one of its bases belongs to a module involved in an import
   loop.

Semantic analysis of types is implemented in module mypy.typeanal.

TODO: Check if the third pass slows down type checking significantly.
  We could probably get rid of it -- for example, we could collect all
  analyzed types in a collection and check them without having to
  traverse the entire AST.
"""

from collections import OrderedDict
from typing import (
    List, Dict, Set, Tuple, cast, TypeVar, Union, Optional, Callable
)

from mypy.nodes import (
    MypyFile, TypeInfo, Node, AssignmentStmt, FuncDef, OverloadedFuncDef,
    ClassDef, Var, GDEF, MODULE_REF, FuncItem, Import, Expression, Lvalue,
    ImportFrom, ImportAll, Block, LDEF, NameExpr, MemberExpr,
    IndexExpr, TupleExpr, ListExpr, ExpressionStmt, ReturnStmt,
    RaiseStmt, AssertStmt, OperatorAssignmentStmt, WhileStmt,
    ForStmt, BreakStmt, ContinueStmt, IfStmt, TryStmt, WithStmt, DelStmt, PassStmt,
    GlobalDecl, SuperExpr, DictExpr, CallExpr, RefExpr, OpExpr, UnaryExpr,
    SliceExpr, CastExpr, RevealTypeExpr, TypeApplication, Context, SymbolTable,
    SymbolTableNode, BOUND_TVAR, UNBOUND_TVAR, ListComprehension, GeneratorExpr,
    LambdaExpr, MDEF, FuncBase, Decorator, SetExpr, TypeVarExpr, NewTypeExpr,
    StrExpr, BytesExpr, PrintStmt, ConditionalExpr, PromoteExpr,
    ComparisonExpr, StarExpr, ARG_POS, ARG_NAMED, ARG_NAMED_OPT, MroError, type_aliases,
    YieldFromExpr, NamedTupleExpr, TypedDictExpr, NonlocalDecl, SymbolNode,
    SetComprehension, DictionaryComprehension, TYPE_ALIAS, TypeAliasExpr,
    YieldExpr, ExecStmt, Argument, BackquoteExpr, ImportBase, AwaitExpr,
    IntExpr, FloatExpr, UnicodeExpr, EllipsisExpr, TempNode, EnumCallExpr,
    COVARIANT, CONTRAVARIANT, INVARIANT, UNBOUND_IMPORTED, LITERAL_YES, ARG_OPT, nongen_builtins,
    collections_type_aliases, get_member_expr_fullname,
)
from mypy.typevars import has_no_typevars, fill_typevars
from mypy.visitor import NodeVisitor
from mypy.traverser import TraverserVisitor
from mypy.errors import Errors, report_internal_error
from mypy.messages import CANNOT_ASSIGN_TO_TYPE
from mypy.types import (
    NoneTyp, CallableType, Overloaded, Instance, Type, TypeVarType, AnyType,
    FunctionLike, UnboundType, TypeList, TypeVarDef, TypeType,
    TupleType, UnionType, StarType, EllipsisType, function_type, TypedDictType,
)
from mypy.nodes import implicit_module_attrs
from mypy.typeanal import (
    TypeAnalyser, TypeAnalyserPass3, analyze_type_alias, no_subscript_builtin_alias,
)
from mypy.exprtotype import expr_to_unanalyzed_type, TypeTranslationError
from mypy.sametypes import is_same_type
from mypy.options import Options
from mypy import join


T = TypeVar('T')


# Inferred truth value of an expression.
ALWAYS_TRUE = 1
MYPY_TRUE = 2  # True in mypy, False at runtime
ALWAYS_FALSE = 3
MYPY_FALSE = 4  # False in mypy, True at runtime
TRUTH_VALUE_UNKNOWN = 5

inverted_truth_mapping = {
    ALWAYS_TRUE: ALWAYS_FALSE,
    ALWAYS_FALSE: ALWAYS_TRUE,
    TRUTH_VALUE_UNKNOWN: TRUTH_VALUE_UNKNOWN,
    MYPY_TRUE: MYPY_FALSE,
    MYPY_FALSE: MYPY_TRUE,
}

# Map from obsolete name to the current spelling.
obsolete_name_mapping = {
    'typing.Function': 'typing.Callable',
    'typing.typevar': 'typing.TypeVar',
}

# Hard coded type promotions (shared between all Python versions).
# These add extra ad-hoc edges to the subtyping relation. For example,
# int is considered a subtype of float, even though there is no
# subclass relationship.
TYPE_PROMOTIONS = {
    'builtins.int': 'builtins.float',
    'builtins.float': 'builtins.complex',
}

# Hard coded type promotions for Python 3.
#
# Note that the bytearray -> bytes promotion is a little unsafe
# as some functions only accept bytes objects. Here convenience
# trumps safety.
TYPE_PROMOTIONS_PYTHON3 = TYPE_PROMOTIONS.copy()
TYPE_PROMOTIONS_PYTHON3.update({
    'builtins.bytearray': 'builtins.bytes',
})

# Hard coded type promotions for Python 2.
#
# These promotions are unsafe, but we are doing them anyway
# for convenience and also for Python 3 compatibility
# (bytearray -> str).
TYPE_PROMOTIONS_PYTHON2 = TYPE_PROMOTIONS.copy()
TYPE_PROMOTIONS_PYTHON2.update({
    'builtins.str': 'builtins.unicode',
    'builtins.bytearray': 'builtins.str',
})

# When analyzing a function, should we analyze the whole function in one go, or
# should we only perform one phase of the analysis? The latter is used for
# nested functions. In the first phase we add the function to the symbol table
# but don't process body. In the second phase we process function body. This
# way we can have mutually recursive nested functions.
FUNCTION_BOTH_PHASES = 0  # Everthing in one go
FUNCTION_FIRST_PHASE_POSTPONE_SECOND = 1  # Add to symbol table but postpone body
FUNCTION_SECOND_PHASE = 2  # Only analyze body


class SemanticAnalyzer(NodeVisitor):
    """Semantically analyze parsed mypy files.

    The analyzer binds names and does various consistency checks for a
    parse tree. Note that type checking is performed as a separate
    pass.

    This is the second phase of semantic analysis.
    """

    # Library search paths
    lib_path = None  # type: List[str]
    # Module name space
    modules = None  # type: Dict[str, MypyFile]
    # Global name space for current module
    globals = None  # type: SymbolTable
    # Names declared using "global" (separate set for each scope)
    global_decls = None  # type: List[Set[str]]
    # Names declated using "nonlocal" (separate set for each scope)
    nonlocal_decls = None  # type: List[Set[str]]
    # Local names of function scopes; None for non-function scopes.
    locals = None  # type: List[SymbolTable]
    # Nested block depths of scopes
    block_depth = None  # type: List[int]
    # TypeInfo of directly enclosing class (or None)
    type = None  # type: TypeInfo
    # Stack of outer classes (the second tuple item contains tvars).
    type_stack = None  # type: List[TypeInfo]
    # Type variables that are bound by the directly enclosing class
    bound_tvars = None  # type: List[SymbolTableNode]
    # Stack of type variables that were bound by outer classess
    tvar_stack = None  # type: List[List[SymbolTableNode]]
    # Per-module options
    options = None  # type: Options

    # Stack of functions being analyzed
    function_stack = None  # type: List[FuncItem]
    # Stack of next available function type variable ids
    next_function_tvar_id_stack = None  # type: List[int]

    # Status of postponing analysis of nested function bodies. By using this we
    # can have mutually recursive nested functions. Values are FUNCTION_x
    # constants. Note that separate phasea are not used for methods.
    postpone_nested_functions_stack = None  # type: List[int]
    # Postponed functions collected if
    # postpone_nested_functions_stack[-1] == FUNCTION_FIRST_PHASE_POSTPONE_SECOND.
    postponed_functions_stack = None  # type: List[List[Node]]

    loop_depth = 0         # Depth of breakable loops
    cur_mod_id = ''        # Current module id (or None) (phase 2)
    is_stub_file = False   # Are we analyzing a stub file?
    imports = None  # type: Set[str]  # Imported modules (during phase 2 analysis)
    errors = None  # type: Errors     # Keeps track of generated errors

    def __init__(self,
                 modules: Dict[str, MypyFile],
                 missing_modules: Set[str],
                 lib_path: List[str], errors: Errors) -> None:
        """Construct semantic analyzer.

        Use lib_path to search for modules, and report analysis errors
        using the Errors instance.
        """
        self.locals = [None]
        self.imports = set()
        self.type = None
        self.type_stack = []
        self.bound_tvars = None
        self.tvar_stack = []
        self.function_stack = []
        self.next_function_tvar_id_stack = [-1]
        self.block_depth = [0]
        self.loop_depth = 0
        self.lib_path = lib_path
        self.errors = errors
        self.modules = modules
        self.missing_modules = missing_modules
        self.postpone_nested_functions_stack = [FUNCTION_BOTH_PHASES]
        self.postponed_functions_stack = []
        self.all_exports = set()  # type: Set[str]

    def visit_file(self, file_node: MypyFile, fnam: str, options: Options) -> None:
        self.options = options
        self.errors.set_file(fnam)
        self.cur_mod_node = file_node
        self.cur_mod_id = file_node.fullname()
        self.is_stub_file = fnam.lower().endswith('.pyi')
        self.globals = file_node.names

        if 'builtins' in self.modules:
            self.globals['__builtins__'] = SymbolTableNode(
                MODULE_REF, self.modules['builtins'], self.cur_mod_id)

        for name in implicit_module_attrs:
            v = self.globals[name].node
            if isinstance(v, Var):
                v.type = self.anal_type(v.type)
                v.is_ready = True

        defs = file_node.defs
        for d in defs:
            self.accept(d)

        if self.cur_mod_id == 'builtins':
            remove_imported_names_from_symtable(self.globals, 'builtins')
            for alias_name in ['List', 'Dict', 'Set']:
                self.globals.pop(alias_name, None)

        if '__all__' in self.globals:
            for name, g in self.globals.items():
                if name not in self.all_exports:
                    g.module_public = False

        del self.options

    def visit_func_def(self, defn: FuncDef) -> None:
        phase_info = self.postpone_nested_functions_stack[-1]
        if phase_info != FUNCTION_SECOND_PHASE:
            self.function_stack.append(defn)
            # First phase of analysis for function.
            self.errors.push_function(defn.name())
            self.update_function_type_variables(defn)
            self.errors.pop_function()
            self.function_stack.pop()

            defn.is_conditional = self.block_depth[-1] > 0

            # TODO(jukka): Figure out how to share the various cases. It doesn't
            #   make sense to have (almost) duplicate code (here and elsewhere) for
            #   3 cases: module-level, class-level and local names. Maybe implement
            #   a common stack of namespaces. As the 3 kinds of namespaces have
            #   different semantics, this wouldn't always work, but it might still
            #   be a win.
            if self.is_class_scope():
                # Method definition
                defn.info = self.type
                if not defn.is_decorated and not defn.is_overload:
                    if defn.name() in self.type.names:
                        # Redefinition. Conditional redefinition is okay.
                        n = self.type.names[defn.name()].node
                        if not self.set_original_def(n, defn):
                            self.name_already_defined(defn.name(), defn)
                    self.type.names[defn.name()] = SymbolTableNode(MDEF, defn)
                self.prepare_method_signature(defn)
            elif self.is_func_scope():
                # Nested function
                if not defn.is_decorated and not defn.is_overload:
                    if defn.name() in self.locals[-1]:
                        # Redefinition. Conditional redefinition is okay.
                        n = self.locals[-1][defn.name()].node
                        if not self.set_original_def(n, defn):
                            self.name_already_defined(defn.name(), defn)
                    else:
                        self.add_local(defn, defn)
            else:
                # Top-level function
                if not defn.is_decorated and not defn.is_overload:
                    symbol = self.globals.get(defn.name())
                    if isinstance(symbol.node, FuncDef) and symbol.node != defn:
                        # This is redefinition. Conditional redefinition is okay.
                        if not self.set_original_def(symbol.node, defn):
                            # Report error.
                            self.check_no_global(defn.name(), defn, True)
            if phase_info == FUNCTION_FIRST_PHASE_POSTPONE_SECOND:
                # Postpone this function (for the second phase).
                self.postponed_functions_stack[-1].append(defn)
                return
        if phase_info != FUNCTION_FIRST_PHASE_POSTPONE_SECOND:
            # Second phase of analysis for function.
            self.errors.push_function(defn.name())
            self.analyze_function(defn)
            if defn.is_coroutine and isinstance(defn.type, CallableType):
                if defn.is_async_generator:
                    # Async generator types are handled elsewhere
                    pass
                else:
                    # A coroutine defined as `async def foo(...) -> T: ...`
                    # has external return type `Awaitable[T]`.
                    defn.type = defn.type.copy_modified(
                        ret_type = self.named_type_or_none('typing.Awaitable',
                                                           [defn.type.ret_type]))
            self.errors.pop_function()

    def prepare_method_signature(self, func: FuncDef) -> None:
        """Check basic signature validity and tweak annotation of self/cls argument."""
        # Only non-static methods are special.
        functype = func.type
        if not func.is_static:
            if not func.arguments:
                self.fail('Method must have at least one argument', func)
            elif isinstance(functype, CallableType):
                self_type = functype.arg_types[0]
                if isinstance(self_type, AnyType):
                    if func.is_class or func.name() in ('__new__', '__init_subclass__'):
                        leading_type = self.class_type(self.type)
                    else:
                        leading_type = fill_typevars(self.type)
                    func.type = replace_implicit_first_type(functype, leading_type)

    def set_original_def(self, previous: Node, new: FuncDef) -> bool:
        """If 'new' conditionally redefine 'previous', set 'previous' as original

        We reject straight redefinitions of functions, as they are usually
        a programming error. For example:

        . def f(): ...
        . def f(): ...  # Error: 'f' redefined
        """
        if isinstance(previous, (FuncDef, Var)) and new.is_conditional:
            new.original_def = previous
            return True
        else:
            return False

    def update_function_type_variables(self, defn: FuncDef) -> None:
        """Make any type variables in the signature of defn explicit.

        Update the signature of defn to contain type variable definitions
        if defn is generic.
        """
        if defn.type:
            assert isinstance(defn.type, CallableType)
            typevars = self.infer_type_variables(defn.type)
            # Do not define a new type variable if already defined in scope.
            typevars = [(name, tvar) for name, tvar in typevars
                        if not self.is_defined_type_var(name, defn)]
            if typevars:
                next_tvar_id = self.next_function_tvar_id()
                defs = [TypeVarDef(tvar[0], next_tvar_id - i,
                                   tvar[1].values, tvar[1].upper_bound,
                                   tvar[1].variance)
                        for i, tvar in enumerate(typevars)]
                defn.type.variables = defs

    def infer_type_variables(self,
                             type: CallableType) -> List[Tuple[str, TypeVarExpr]]:
        """Return list of unique type variables referred to in a callable."""
        names = []  # type: List[str]
        tvars = []  # type: List[TypeVarExpr]
        for arg in type.arg_types + [type.ret_type]:
            for name, tvar_expr in self.find_type_variables_in_type(arg):
                if name not in names:
                    names.append(name)
                    tvars.append(tvar_expr)
        return list(zip(names, tvars))

    def find_type_variables_in_type(self, type: Type) -> List[Tuple[str, TypeVarExpr]]:
        """Return a list of all unique type variable references in type.

        This effectively does partial name binding, results of which are mostly thrown away.
        """
        result = []  # type: List[Tuple[str, TypeVarExpr]]
        if isinstance(type, UnboundType):
            name = type.name
            node = self.lookup_qualified(name, type)
            if node and node.kind == UNBOUND_TVAR:
                assert isinstance(node.node, TypeVarExpr)
                result.append((name, node.node))
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
        elif isinstance(type, EllipsisType) or isinstance(type, TupleType):
            pass
        else:
            assert False, 'Unsupported type %s' % type
        return result

    def is_defined_type_var(self, tvar: str, context: Context) -> bool:
        return self.lookup_qualified(tvar, context).kind == BOUND_TVAR

    def visit_overloaded_func_def(self, defn: OverloadedFuncDef) -> None:
        # OverloadedFuncDef refers to any legitimate situation where you have
        # more than one declaration for the same function in a row.  This occurs
        # with a @property with a setter or a deleter, and for a classic
        # @overload.

        # Decide whether to analyze this as a property or an overload.  If an
        # overload, and we're outside a stub, find the impl and set it.  Remove
        # the impl from the item list, it's special.
        types = []  # type: List[CallableType]
        non_overload_indexes = []

        # See if the first item is a property (and not an overload)
        first_item = defn.items[0]
        first_item.is_overload = True
        first_item.accept(self)

        if isinstance(first_item, Decorator) and first_item.func.is_property:
            first_item.func.is_overload = True
            self.analyze_property_with_multi_part_definition(defn)
            typ = function_type(first_item.func, self.builtin_type('builtins.function'))
            assert isinstance(typ, CallableType)
            types = [typ]
        else:
            for i, item in enumerate(defn.items):
                if i != 0:
                    # The first item was already visited
                    item.is_overload = True
                    item.accept(self)
                # TODO support decorated overloaded functions properly
                if isinstance(item, Decorator):
                    callable = function_type(item.func, self.builtin_type('builtins.function'))
                    assert isinstance(callable, CallableType)
                    if not any(refers_to_fullname(dec, 'typing.overload')
                               for dec in item.decorators):
                        if i == len(defn.items) - 1 and not self.is_stub_file:
                            # Last item outside a stub is impl
                            defn.impl = item
                        else:
                            # Oops it wasn't an overload after all. A clear error
                            # will vary based on where in the list it is, record
                            # that.
                            non_overload_indexes.append(i)
                    else:
                        item.func.is_overload = True
                        types.append(callable)
                elif isinstance(item, FuncDef):
                    if i == len(defn.items) - 1 and not self.is_stub_file:
                        defn.impl = item
                    else:
                        non_overload_indexes.append(i)
            if non_overload_indexes:
                if types:
                    # Some of them were overloads, but not all.
                    for idx in non_overload_indexes:
                        if self.is_stub_file:
                            self.fail("An implementation for an overloaded function "
                                      "is not allowed in a stub file", defn.items[idx])
                        else:
                            self.fail("The implementation for an overloaded function "
                                      "must come last", defn.items[idx])
                else:
                    for idx in non_overload_indexes[1:]:
                        self.name_already_defined(defn.name(), defn.items[idx])
                    if defn.impl:
                        self.name_already_defined(defn.name(), defn.impl)
                # Remove the non-overloads
                for idx in reversed(non_overload_indexes):
                    del defn.items[idx]
            # If we found an implementation, remove it from the overloads to
            # consider.
            if defn.impl is not None:
                assert defn.impl is defn.items[-1]
                defn.items = defn.items[:-1]

            elif not self.is_stub_file and not non_overload_indexes:
                self.fail(
                    "An overloaded function outside a stub file must have an implementation",
                    defn)

        if types:
            defn.type = Overloaded(types)
            defn.type.line = defn.line

        if self.is_class_scope():
            self.type.names[defn.name()] = SymbolTableNode(MDEF, defn,
                                                           typ=defn.type)
            defn.info = self.type
        elif self.is_func_scope():
            self.add_local(defn, defn)

    def analyze_property_with_multi_part_definition(self, defn: OverloadedFuncDef) -> None:
        """Analyze a property defined using multiple methods (e.g., using @x.setter).

        Assume that the first method (@property) has already been analyzed.
        """
        defn.is_property = True
        items = defn.items
        first_item = cast(Decorator, defn.items[0])
        for item in items[1:]:
            if isinstance(item, Decorator) and len(item.decorators) == 1:
                node = item.decorators[0]
                if isinstance(node, MemberExpr):
                    if node.name == 'setter':
                        # The first item represents the entire property.
                        first_item.var.is_settable_property = True
                        # Get abstractness from the original definition.
                        item.func.is_abstract = first_item.func.is_abstract
                item.func.accept(self)
            else:
                self.fail("Decorated property not supported", item)

    def next_function_tvar_id(self) -> int:
        return self.next_function_tvar_id_stack[-1]

    def analyze_function(self, defn: FuncItem) -> None:
        is_method = self.is_class_scope()

        tvarnodes = self.add_func_type_variables_to_symbol_table(defn)
        next_function_tvar_id = min([self.next_function_tvar_id()] +
                                    [n.tvar_def.id.raw_id - 1 for n in tvarnodes])
        self.next_function_tvar_id_stack.append(next_function_tvar_id)

        if defn.type:
            # Signature must be analyzed in the surrounding scope so that
            # class-level imported names and type variables are in scope.
            self.check_classvar_in_signature(defn.type)
            defn.type = self.anal_type(defn.type)
            self.check_function_signature(defn)
            if isinstance(defn, FuncDef):
                defn.type = set_callable_name(defn.type, defn)
        for arg in defn.arguments:
            if arg.initializer:
                arg.initializer.accept(self)
        self.function_stack.append(defn)
        self.enter()
        for arg in defn.arguments:
            self.add_local(arg.variable, defn)
        for arg in defn.arguments:
            if arg.initialization_statement:
                lvalue = arg.initialization_statement.lvalues[0]
                lvalue.accept(self)

        # The first argument of a non-static, non-class method is like 'self'
        # (though the name could be different), having the enclosing class's
        # instance type.
        if is_method and not defn.is_static and not defn.is_class and defn.arguments:
            defn.arguments[0].variable.is_self = True

        # First analyze body of the function but ignore nested functions.
        self.postpone_nested_functions_stack.append(FUNCTION_FIRST_PHASE_POSTPONE_SECOND)
        self.postponed_functions_stack.append([])
        defn.body.accept(self)

        # Analyze nested functions (if any) as a second phase.
        self.postpone_nested_functions_stack[-1] = FUNCTION_SECOND_PHASE
        for postponed in self.postponed_functions_stack[-1]:
            postponed.accept(self)
        self.postpone_nested_functions_stack.pop()
        self.postponed_functions_stack.pop()

        self.next_function_tvar_id_stack.pop()
        disable_typevars(tvarnodes)

        self.leave()
        self.function_stack.pop()

    def check_classvar_in_signature(self, typ: Type) -> None:
        t = None  # type: Type
        if isinstance(typ, Overloaded):
            for t in typ.items():
                self.check_classvar_in_signature(t)
            return
        if not isinstance(typ, CallableType):
            return
        for t in typ.arg_types + [typ.ret_type]:
            if self.is_classvar(t):
                self.fail_invalid_classvar(t)
                # Show only one error per signature
                break

    def add_func_type_variables_to_symbol_table(
            self, defn: FuncItem) -> List[SymbolTableNode]:
        nodes = []  # type: List[SymbolTableNode]
        if defn.type:
            tt = defn.type
            assert isinstance(tt, CallableType)
            items = tt.variables
            names = self.type_var_names()
            for item in items:
                name = item.name
                if name in names:
                    self.name_already_defined(name, defn)
                node = self.bind_type_var(name, item, defn)
                nodes.append(node)
                names.add(name)
        return nodes

    def type_var_names(self) -> Set[str]:
        if not self.type:
            return set()
        else:
            return set(self.type.type_vars)

    def bind_type_var(self, fullname: str, tvar_def: TypeVarDef,
                     context: Context) -> SymbolTableNode:
        node = self.lookup_qualified(fullname, context)
        node.kind = BOUND_TVAR
        node.tvar_def = tvar_def
        return node

    def check_function_signature(self, fdef: FuncItem) -> None:
        sig = fdef.type
        assert isinstance(sig, CallableType)
        if len(sig.arg_types) < len(fdef.arguments):
            self.fail('Type signature has too few arguments', fdef)
            # Add dummy Any arguments to prevent crashes later.
            extra_anys = [AnyType()] * (len(fdef.arguments) - len(sig.arg_types))
            sig.arg_types.extend(extra_anys)
        elif len(sig.arg_types) > len(fdef.arguments):
            self.fail('Type signature has too many arguments', fdef, blocker=True)

    def visit_class_def(self, defn: ClassDef) -> None:
        self.clean_up_bases_and_infer_type_variables(defn)
        if self.analyze_typeddict_classdef(defn):
            return
        if self.analyze_namedtuple_classdef(defn):
            # just analyze the class body so we catch type errors in default values
            self.enter_class(defn)
            defn.defs.accept(self)
            self.leave_class()
        else:
            self.setup_class_def_analysis(defn)

            self.bind_class_type_vars(defn)

            self.analyze_base_classes(defn)
            self.analyze_metaclass(defn)

            for decorator in defn.decorators:
                self.analyze_class_decorator(defn, decorator)

            self.enter_class(defn)

            # Analyze class body.
            defn.defs.accept(self)

            self.calculate_abstract_status(defn.info)
            self.setup_type_promotion(defn)

            self.leave_class()

            self.unbind_class_type_vars()

    def enter_class(self, defn: ClassDef) -> None:
        # Remember previous active class
        self.type_stack.append(self.type)
        self.locals.append(None)  # Add class scope
        self.block_depth.append(-1)  # The class body increments this to 0
        self.postpone_nested_functions_stack.append(FUNCTION_BOTH_PHASES)
        self.type = defn.info

    def leave_class(self) -> None:
        """ Restore analyzer state. """
        self.postpone_nested_functions_stack.pop()
        self.block_depth.pop()
        self.locals.pop()
        self.type = self.type_stack.pop()

    def bind_class_type_vars(self, defn: ClassDef) -> None:
        """ Unbind type variables of previously active class and bind
        the type variables for the active class.
        """
        if self.bound_tvars:
            disable_typevars(self.bound_tvars)
        self.tvar_stack.append(self.bound_tvars)
        self.bound_tvars = self.bind_class_type_variables_in_symbol_table(defn.info)

    def unbind_class_type_vars(self) -> None:
        """ Unbind the active class' type vars and rebind the
        type vars of the previously active class.
        """
        disable_typevars(self.bound_tvars)
        self.bound_tvars = self.tvar_stack.pop()
        if self.bound_tvars:
            enable_typevars(self.bound_tvars)

    def analyze_class_decorator(self, defn: ClassDef, decorator: Expression) -> None:
        decorator.accept(self)

    def calculate_abstract_status(self, typ: TypeInfo) -> None:
        """Calculate abstract status of a class.

        Set is_abstract of the type to True if the type has an unimplemented
        abstract attribute.  Also compute a list of abstract attributes.
        """
        concrete = set()  # type: Set[str]
        abstract = []  # type: List[str]
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

    def setup_type_promotion(self, defn: ClassDef) -> None:
        """Setup extra, ad-hoc subtyping relationships between classes (promotion).

        This includes things like 'int' being compatible with 'float'.
        """
        promote_target = None  # type: Type
        for decorator in defn.decorators:
            if isinstance(decorator, CallExpr):
                analyzed = decorator.analyzed
                if isinstance(analyzed, PromoteExpr):
                    # _promote class decorator (undocumented faeture).
                    promote_target = analyzed.type
        if not promote_target:
            promotions = (TYPE_PROMOTIONS_PYTHON3 if self.options.python_version[0] >= 3
                          else TYPE_PROMOTIONS_PYTHON2)
            if defn.fullname in promotions:
                promote_target = self.named_type_or_none(promotions[defn.fullname])
        defn.info._promote = promote_target

    def clean_up_bases_and_infer_type_variables(self, defn: ClassDef) -> None:
        """Remove extra base classes such as Generic and infer type vars.

        For example, consider this class:

        . class Foo(Bar, Generic[T]): ...

        Now we will remove Generic[T] from bases of Foo and infer that the
        type variable 'T' is a type argument of Foo.

        Note that this is performed *before* semantic analysis.
        """
        removed = []  # type: List[int]
        declared_tvars = []  # type: List[Tuple[str, TypeVarExpr]]
        type_vars = []  # type: List[TypeVarDef]
        for i, base_expr in enumerate(defn.base_type_exprs):
            try:
                base = expr_to_unanalyzed_type(base_expr)
            except TypeTranslationError:
                # This error will be caught later.
                continue
            tvars = self.analyze_typevar_declaration(base)
            if tvars is not None:
                if declared_tvars:
                    self.fail('Duplicate Generic in bases', defn)
                removed.append(i)
                declared_tvars.extend(tvars)

        all_tvars = self.get_all_bases_tvars(defn, removed)
        if declared_tvars:
            if len(self.remove_dups(declared_tvars)) < len(declared_tvars):
                self.fail("Duplicate type variables in Generic[...]", defn)
            declared_tvars = self.remove_dups(declared_tvars)
            if not set(all_tvars).issubset(set(declared_tvars)):
                self.fail("If Generic[...] is present it should list all type variables", defn)
                # In case of error, Generic tvars will go first
                declared_tvars = self.remove_dups(declared_tvars + all_tvars)
        else:
            declared_tvars = all_tvars
        for j, (name, tvar_expr) in enumerate(declared_tvars):
            type_vars.append(TypeVarDef(name, j + 1, tvar_expr.values,
                                        tvar_expr.upper_bound, tvar_expr.variance))
        if type_vars:
            defn.type_vars = type_vars
            if defn.info:
                defn.info.type_vars = [tv.name for tv in type_vars]
        for i in reversed(removed):
            del defn.base_type_exprs[i]

    def analyze_typevar_declaration(self, t: Type) -> Optional[List[Tuple[str, TypeVarExpr]]]:
        if not isinstance(t, UnboundType):
            return None
        unbound = t
        sym = self.lookup_qualified(unbound.name, unbound)
        if sym is None or sym.node is None:
            return None
        if sym.node.fullname() == 'typing.Generic':
            tvars = []  # type: List[Tuple[str, TypeVarExpr]]
            for arg in unbound.args:
                tvar = self.analyze_unbound_tvar(arg)
                if tvar:
                    tvars.append(tvar)
                else:
                    self.fail('Free type variable expected in %s[...]' %
                              sym.node.name(), t)
            return tvars
        return None

    def analyze_unbound_tvar(self, t: Type) -> Tuple[str, TypeVarExpr]:
        if not isinstance(t, UnboundType):
            return None
        unbound = t
        sym = self.lookup_qualified(unbound.name, unbound)
        if sym is not None and sym.kind == UNBOUND_TVAR:
            assert isinstance(sym.node, TypeVarExpr)
            return unbound.name, sym.node
        return None

    def get_all_bases_tvars(self, defn: ClassDef,
                            removed: List[int]) -> List[Tuple[str, TypeVarExpr]]:
        tvars = []  # type: List[Tuple[str, TypeVarExpr]]
        for i, base_expr in enumerate(defn.base_type_exprs):
            if i not in removed:
                try:
                    base = expr_to_unanalyzed_type(base_expr)
                except TypeTranslationError:
                    # This error will be caught later.
                    continue
                tvars.extend(self.get_tvars(base))
        return self.remove_dups(tvars)

    def get_tvars(self, tp: Type) -> List[Tuple[str, TypeVarExpr]]:
        tvars = []  # type: List[Tuple[str, TypeVarExpr]]
        if isinstance(tp, UnboundType):
            tp_args = tp.args
        elif isinstance(tp, TypeList):
            tp_args = tp.items
        else:
            return tvars
        for arg in tp_args:
            tvar = self.analyze_unbound_tvar(arg)
            if tvar:
                tvars.append(tvar)
            else:
                tvars.extend(self.get_tvars(arg))
        return self.remove_dups(tvars)

    def remove_dups(self, tvars: List[T]) -> List[T]:
        # Get unique elements in order of appearance
        all_tvars = set(tvars)
        new_tvars = []  # type: List[T]
        for t in tvars:
            if t in all_tvars:
                new_tvars.append(t)
                all_tvars.remove(t)
        return new_tvars

    def analyze_namedtuple_classdef(self, defn: ClassDef) -> bool:
        # special case for NamedTuple
        for base_expr in defn.base_type_exprs:
            if isinstance(base_expr, RefExpr):
                base_expr.accept(self)
                if base_expr.fullname == 'typing.NamedTuple':
                    node = self.lookup(defn.name, defn)
                    if node is not None:
                        node.kind = GDEF  # TODO in process_namedtuple_definition also applies here
                        items, types, default_items = self.check_namedtuple_classdef(defn)
                        node.node = self.build_namedtuple_typeinfo(
                            defn.name, items, types, default_items)
                        return True
        return False

    def check_namedtuple_classdef(
            self, defn: ClassDef) -> Tuple[List[str], List[Type], Dict[str, Expression]]:
        NAMEDTUP_CLASS_ERROR = ('Invalid statement in NamedTuple definition; '
                               'expected "field_name: field_type"')
        if self.options.python_version < (3, 6):
            self.fail('NamedTuple class syntax is only supported in Python 3.6', defn)
            return [], [], {}
        if len(defn.base_type_exprs) > 1:
            self.fail('NamedTuple should be a single base', defn)
        items = []  # type: List[str]
        types = []  # type: List[Type]
        default_items = {}  # type: Dict[str, Expression]
        for stmt in defn.defs.body:
            if not isinstance(stmt, AssignmentStmt):
                # Still allow pass or ... (for empty namedtuples).
                if (not isinstance(stmt, PassStmt) and
                    not (isinstance(stmt, ExpressionStmt) and
                         isinstance(stmt.expr, EllipsisExpr))):
                    self.fail(NAMEDTUP_CLASS_ERROR, stmt)
            elif len(stmt.lvalues) > 1 or not isinstance(stmt.lvalues[0], NameExpr):
                # An assignment, but an invalid one.
                self.fail(NAMEDTUP_CLASS_ERROR, stmt)
            else:
                # Append name and type in this case...
                name = stmt.lvalues[0].name
                items.append(name)
                types.append(AnyType() if stmt.type is None else self.anal_type(stmt.type))
                # ...despite possible minor failures that allow further analyzis.
                if name.startswith('_'):
                    self.fail('NamedTuple field name cannot start with an underscore: {}'
                              .format(name), stmt)
                if stmt.type is None or hasattr(stmt, 'new_syntax') and not stmt.new_syntax:
                    self.fail(NAMEDTUP_CLASS_ERROR, stmt)
                elif isinstance(stmt.rvalue, TempNode):
                    # x: int assigns rvalue to TempNode(AnyType())
                    if default_items:
                        self.fail('Non-default NamedTuple fields cannot follow default fields',
                                  stmt)
                else:
                    default_items[name] = stmt.rvalue
        return items, types, default_items

    def setup_class_def_analysis(self, defn: ClassDef) -> None:
        """Prepare for the analysis of a class definition."""
        if not defn.info:
            defn.info = TypeInfo(SymbolTable(), defn, self.cur_mod_id)
            defn.info._fullname = defn.info.name()
        if self.is_func_scope() or self.type:
            kind = MDEF
            if self.is_func_scope():
                kind = LDEF
            node = SymbolTableNode(kind, defn.info)
            self.add_symbol(defn.name, node, defn)
            if kind == LDEF:
                # We need to preserve local classes, let's store them
                # in globals under mangled unique names
                local_name = defn.info._fullname + '@' + str(defn.line)
                defn.info._fullname = self.cur_mod_id + '.' + local_name
                defn.fullname = defn.info._fullname
                self.globals[local_name] = node

    def analyze_base_classes(self, defn: ClassDef) -> None:
        """Analyze and set up base classes.

        This computes several attributes on the corresponding TypeInfo defn.info
        related to the base classes: defn.info.bases, defn.info.mro, and
        miscellaneous others (at least tuple_type, fallback_to_any, and is_enum.)
        """

        base_types = []  # type: List[Instance]
        info = defn.info
        for base_expr in defn.base_type_exprs:
            try:
                base = self.expr_to_analyzed_type(base_expr)
            except TypeTranslationError:
                self.fail('Invalid base class', base_expr)
                info.fallback_to_any = True
                continue

            if isinstance(base, TupleType):
                if info.tuple_type:
                    self.fail("Class has two incompatible bases derived from tuple", defn)
                    defn.has_incompatible_baseclass = True
                info.tuple_type = base
                base_types.append(base.fallback)
            elif isinstance(base, Instance):
                if base.type.is_newtype:
                    self.fail("Cannot subclass NewType", defn)
                base_types.append(base)
            elif isinstance(base, AnyType):
                if self.options.disallow_subclassing_any:
                    if isinstance(base_expr, (NameExpr, MemberExpr)):
                        msg = "Class cannot subclass '{}' (has type 'Any')".format(base_expr.name)
                    else:
                        msg = "Class cannot subclass value of type 'Any'"
                    self.fail(msg, base_expr)
                info.fallback_to_any = True
            else:
                self.fail('Invalid base class', base_expr)
                info.fallback_to_any = True

        # Add 'object' as implicit base if there is no other base class.
        if (not base_types and defn.fullname != 'builtins.object'):
            base_types.append(self.object_type())

        info.bases = base_types

        # Calculate the MRO. It might be incomplete at this point if
        # the bases of defn include classes imported from other
        # modules in an import loop. We'll recompute it in ThirdPass.
        if not self.verify_base_classes(defn):
            # Give it an MRO consisting of just the class itself and object.
            defn.info.mro = [defn.info, self.object_type().type]
            return
        calculate_class_mro(defn, self.fail_blocker)
        # If there are cyclic imports, we may be missing 'object' in
        # the MRO. Fix MRO if needed.
        if info.mro and info.mro[-1].fullname() != 'builtins.object':
            info.mro.append(self.object_type().type)

    def expr_to_analyzed_type(self, expr: Expression) -> Type:
        if isinstance(expr, CallExpr):
            expr.accept(self)
            info = self.check_namedtuple(expr)
            if info is None:
                # Some form of namedtuple is the only valid type that looks like a call
                # expression. This isn't a valid type.
                raise TypeTranslationError()
            fallback = Instance(info, [])
            return TupleType(info.tuple_type.items, fallback=fallback)
        typ = expr_to_unanalyzed_type(expr)
        return self.anal_type(typ)

    def verify_base_classes(self, defn: ClassDef) -> bool:
        info = defn.info
        for base in info.bases:
            baseinfo = base.type
            if self.is_base_class(info, baseinfo):
                self.fail('Cycle in inheritance hierarchy', defn, blocker=True)
                # Clear bases to forcefully get rid of the cycle.
                info.bases = []
            if baseinfo.fullname() == 'builtins.bool':
                self.fail("'%s' is not a valid base class" %
                          baseinfo.name(), defn, blocker=True)
                return False
        dup = find_duplicate(info.direct_base_classes())
        if dup:
            self.fail('Duplicate base class "%s"' % dup.name(), defn, blocker=True)
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
        error_context = defn  # type: Context
        if defn.metaclass is None and self.options.python_version[0] == 2:
            # Look for "__metaclass__ = <metaclass>" in Python 2.
            for body_node in defn.defs.body:
                if isinstance(body_node, ClassDef) and body_node.name == "__metaclass__":
                    self.fail("Metaclasses defined as inner classes are not supported", body_node)
                    return
                elif isinstance(body_node, AssignmentStmt) and len(body_node.lvalues) == 1:
                    lvalue = body_node.lvalues[0]
                    if isinstance(lvalue, NameExpr) and lvalue.name == "__metaclass__":
                        error_context = body_node.rvalue
                        if isinstance(body_node.rvalue, NameExpr):
                            name = body_node.rvalue.name
                        elif isinstance(body_node.rvalue, MemberExpr):
                            name = get_member_expr_fullname(body_node.rvalue)
                        else:
                            name = None
                        if name:
                            defn.metaclass = name
                        else:
                            self.fail(
                                "Dynamic metaclass not supported for '%s'" % defn.name,
                                body_node
                            )
                            return
        if defn.metaclass:
            if defn.metaclass == '<error>':
                self.fail("Dynamic metaclass not supported for '%s'" % defn.name, error_context)
                return
            sym = self.lookup_qualified(defn.metaclass, error_context)
            if sym is None:
                # Probably a name error - it is already handled elsewhere
                return
            if isinstance(sym.node, Var) and isinstance(sym.node.type, AnyType):
                # 'Any' metaclass -- just ignore it.
                #
                # TODO: A better approach would be to record this information
                #       and assume that the type object supports arbitrary
                #       attributes, similar to an 'Any' base class.
                return
            if not isinstance(sym.node, TypeInfo) or sym.node.tuple_type is not None:
                self.fail("Invalid metaclass '%s'" % defn.metaclass, defn)
                return
            if not sym.node.is_metaclass():
                self.fail("Metaclasses not inheriting from 'type' are not supported", defn)
                return
            inst = fill_typevars(sym.node)
            assert isinstance(inst, Instance)
            defn.info.declared_metaclass = inst
        defn.info.metaclass_type = defn.info.calculate_metaclass_type()
        if defn.info.metaclass_type is None:
            # Inconsistency may happen due to multiple baseclasses even in classes that
            # do not declare explicit metaclass, but it's harder to catch at this stage
            if defn.metaclass:
                self.fail("Inconsistent metaclass structure for '%s'" % defn.name, defn)

    def object_type(self) -> Instance:
        return self.named_type('__builtins__.object')

    def str_type(self) -> Instance:
        return self.named_type('__builtins__.str')

    def class_type(self, info: TypeInfo) -> Type:
        # Construct a function type whose fallback is cls.
        from mypy import checkmember  # To avoid import cycle.
        leading_type = checkmember.type_object_type(info, self.builtin_type)
        if isinstance(leading_type, Overloaded):
            # Overloaded __init__ is too complex to handle.  Plus it's stubs only.
            return AnyType()
        else:
            return leading_type

    def named_type(self, qualified_name: str, args: List[Type] = None) -> Instance:
        sym = self.lookup_qualified(qualified_name, None)
        assert isinstance(sym.node, TypeInfo)
        return Instance(sym.node, args or [])

    def named_type_or_none(self, qualified_name: str, args: List[Type] = None) -> Instance:
        sym = self.lookup_fully_qualified_or_none(qualified_name)
        if not sym:
            return None
        assert isinstance(sym.node, TypeInfo)
        return Instance(sym.node, args or [])

    def bind_class_type_variables_in_symbol_table(
            self, info: TypeInfo) -> List[SymbolTableNode]:
        nodes = []  # type: List[SymbolTableNode]
        for var, binder in zip(info.type_vars, info.defn.type_vars):
            node = self.bind_type_var(var, binder, info)
            nodes.append(node)
        return nodes

    def is_typeddict(self, expr: Expression) -> bool:
        return (isinstance(expr, RefExpr) and isinstance(expr.node, TypeInfo) and
                expr.node.typeddict_type is not None)

    def analyze_typeddict_classdef(self, defn: ClassDef) -> bool:
        # special case for TypedDict
        possible = False
        for base_expr in defn.base_type_exprs:
            if isinstance(base_expr, RefExpr):
                base_expr.accept(self)
                if (base_expr.fullname == 'mypy_extensions.TypedDict' or
                        self.is_typeddict(base_expr)):
                    possible = True
        if possible:
            node = self.lookup(defn.name, defn)
            if node is not None:
                node.kind = GDEF  # TODO in process_namedtuple_definition also applies here
                if (len(defn.base_type_exprs) == 1 and
                        isinstance(defn.base_type_exprs[0], RefExpr) and
                        defn.base_type_exprs[0].fullname == 'mypy_extensions.TypedDict'):
                    # Building a new TypedDict
                    fields, types = self.check_typeddict_classdef(defn)
                    node.node = self.build_typeddict_typeinfo(defn.name, fields, types)
                    return True
                # Extending/merging existing TypedDicts
                if any(not isinstance(expr, RefExpr) or
                       expr.fullname != 'mypy_extensions.TypedDict' and
                       not self.is_typeddict(expr) for expr in defn.base_type_exprs):
                    self.fail("All bases of a new TypedDict must be TypedDict types", defn)
                typeddict_bases = list(filter(self.is_typeddict, defn.base_type_exprs))
                newfields = []  # type: List[str]
                newtypes = []  # type: List[Type]
                tpdict = None  # type: OrderedDict[str, Type]
                for base in typeddict_bases:
                    assert isinstance(base, RefExpr)
                    assert isinstance(base.node, TypeInfo)
                    assert isinstance(base.node.typeddict_type, TypedDictType)
                    tpdict = base.node.typeddict_type.items
                    newdict = tpdict.copy()
                    for key in tpdict:
                        if key in newfields:
                            self.fail('Cannot overwrite TypedDict field "{}" while merging'
                                      .format(key), defn)
                            newdict.pop(key)
                    newfields.extend(newdict.keys())
                    newtypes.extend(newdict.values())
                fields, types = self.check_typeddict_classdef(defn, newfields)
                newfields.extend(fields)
                newtypes.extend(types)
                node.node = self.build_typeddict_typeinfo(defn.name, newfields, newtypes)
                return True
        return False

    def check_typeddict_classdef(self, defn: ClassDef,
                                 oldfields: List[str] = None) -> Tuple[List[str], List[Type]]:
        TPDICT_CLASS_ERROR = ('Invalid statement in TypedDict definition; '
                              'expected "field_name: field_type"')
        if self.options.python_version < (3, 6):
            self.fail('TypedDict class syntax is only supported in Python 3.6', defn)
            return [], []
        fields = []  # type: List[str]
        types = []  # type: List[Type]
        for stmt in defn.defs.body:
            if not isinstance(stmt, AssignmentStmt):
                # Still allow pass or ... (for empty TypedDict's).
                if (not isinstance(stmt, PassStmt) and
                    not (isinstance(stmt, ExpressionStmt) and
                         isinstance(stmt.expr, EllipsisExpr))):
                    self.fail(TPDICT_CLASS_ERROR, stmt)
            elif len(stmt.lvalues) > 1 or not isinstance(stmt.lvalues[0], NameExpr):
                # An assignment, but an invalid one.
                self.fail(TPDICT_CLASS_ERROR, stmt)
            else:
                name = stmt.lvalues[0].name
                if name in (oldfields or []):
                    self.fail('Cannot overwrite TypedDict field "{}" while extending'
                              .format(name), stmt)
                    continue
                if name in fields:
                    self.fail('Duplicate TypedDict field "{}"'.format(name), stmt)
                    continue
                # Append name and type in this case...
                fields.append(name)
                types.append(AnyType() if stmt.type is None else self.anal_type(stmt.type))
                # ...despite possible minor failures that allow further analyzis.
                if stmt.type is None or hasattr(stmt, 'new_syntax') and not stmt.new_syntax:
                    self.fail(TPDICT_CLASS_ERROR, stmt)
                elif not isinstance(stmt.rvalue, TempNode):
                    # x: int assigns rvalue to TempNode(AnyType())
                    self.fail('Right hand side values are not supported in TypedDict', stmt)
        return fields, types

    def visit_import(self, i: Import) -> None:
        for id, as_id in i.ids:
            if as_id is not None:
                self.add_module_symbol(id, as_id, module_public=True, context=i)
            else:
                # Modules imported in a stub file without using 'as x' won't get exported when
                # doing 'from m import *'.
                module_public = not self.is_stub_file
                base = id.split('.')[0]
                self.add_module_symbol(base, base, module_public=module_public,
                                       context=i)
                self.add_submodules_to_parent_modules(id, module_public)

    def add_submodules_to_parent_modules(self, id: str, module_public: bool) -> None:
        """Recursively adds a reference to a newly loaded submodule to its parent.

        When you import a submodule in any way, Python will add a reference to that
        submodule to its parent. So, if you do something like `import A.B` or
        `from A import B` or `from A.B import Foo`, Python will add a reference to
        module A.B to A's namespace.

        Note that this "parent patching" process is completely independent from any
        changes made to the *importer's* namespace. For example, if you have a file
        named `foo.py` where you do `from A.B import Bar`, then foo's namespace will
        be modified to contain a reference to only Bar. Independently, A's namespace
        will be modified to contain a reference to `A.B`.
        """
        while '.' in id:
            parent, child = id.rsplit('.', 1)
            parent_mod = self.modules.get(parent)
            if parent_mod and child not in parent_mod.names:
                child_mod = self.modules.get(id)
                if child_mod:
                    sym = SymbolTableNode(MODULE_REF, child_mod, parent,
                                          module_public=module_public)
                    parent_mod.names[child] = sym
            id = parent

    def add_module_symbol(self, id: str, as_id: str, module_public: bool,
                          context: Context) -> None:
        if id in self.modules:
            m = self.modules[id]
            self.add_symbol(as_id, SymbolTableNode(MODULE_REF, m, self.cur_mod_id,
                                                   module_public=module_public), context)
        else:
            self.add_unknown_symbol(as_id, context, is_import=True)

    def visit_import_from(self, imp: ImportFrom) -> None:
        import_id = self.correct_relative_import(imp)
        self.add_submodules_to_parent_modules(import_id, True)
        module = self.modules.get(import_id)
        for id, as_id in imp.names:
            node = module.names.get(id) if module else None
            missing = False

            # If the module does not contain a symbol with the name 'id',
            # try checking if it's a module instead.
            if not node or node.kind == UNBOUND_IMPORTED:
                possible_module_id = import_id + '.' + id
                mod = self.modules.get(possible_module_id)
                if mod is not None:
                    node = SymbolTableNode(MODULE_REF, mod, import_id)
                    self.add_submodules_to_parent_modules(possible_module_id, True)
                elif possible_module_id in self.missing_modules:
                    missing = True

            if node and node.kind != UNBOUND_IMPORTED:
                node = self.normalize_type_alias(node, imp)
                if not node:
                    return
                imported_id = as_id or id
                existing_symbol = self.globals.get(imported_id)
                if existing_symbol:
                    # Import can redefine a variable. They get special treatment.
                    if self.process_import_over_existing_name(
                            imported_id, existing_symbol, node, imp):
                        continue
                # 'from m import x as x' exports x in a stub file.
                module_public = not self.is_stub_file or as_id is not None
                symbol = SymbolTableNode(node.kind, node.node,
                                         self.cur_mod_id,
                                         node.type_override,
                                         module_public=module_public,
                                         normalized=node.normalized)
                self.add_symbol(imported_id, symbol, imp)
            elif module and not missing:
                # Missing attribute.
                message = "Module '{}' has no attribute '{}'".format(import_id, id)
                extra = self.undefined_name_extra_info('{}.{}'.format(import_id, id))
                if extra:
                    message += " {}".format(extra)
                self.fail(message, imp)
            else:
                # Missing module.
                self.add_unknown_symbol(as_id or id, imp, is_import=True)

    def process_import_over_existing_name(self,
                                          imported_id: str, existing_symbol: SymbolTableNode,
                                          module_symbol: SymbolTableNode,
                                          import_node: ImportBase) -> bool:
        if (existing_symbol.kind in (LDEF, GDEF, MDEF) and
                isinstance(existing_symbol.node, (Var, FuncDef, TypeInfo))):
            # This is a valid import over an existing definition in the file. Construct a dummy
            # assignment that we'll use to type check the import.
            lvalue = NameExpr(imported_id)
            lvalue.kind = existing_symbol.kind
            lvalue.node = existing_symbol.node
            rvalue = NameExpr(imported_id)
            rvalue.kind = module_symbol.kind
            rvalue.node = module_symbol.node
            assignment = AssignmentStmt([lvalue], rvalue)
            for node in assignment, lvalue, rvalue:
                node.set_line(import_node)
            import_node.assignments.append(assignment)
            return True
        return False

    def normalize_type_alias(self, node: SymbolTableNode,
                             ctx: Context) -> SymbolTableNode:
        normalized = False
        if node.fullname in type_aliases:
            # Node refers to an aliased type such as typing.List; normalize.
            node = self.lookup_qualified(type_aliases[node.fullname], ctx)
            normalized = True
        if node.fullname in collections_type_aliases:
            # Similar, but for types from the collections module like typing.DefaultDict
            self.add_module_symbol('collections', '__mypy_collections__', False, ctx)
            node = self.lookup_qualified(collections_type_aliases[node.fullname], ctx)
            normalized = True
        if normalized:
            node = SymbolTableNode(node.kind, node.node,
                                   node.mod_id, node.type_override, normalized=True)
        return node

    def correct_relative_import(self, node: Union[ImportFrom, ImportAll]) -> str:
        if node.relative == 0:
            return node.id

        parts = self.cur_mod_id.split(".")
        cur_mod_id = self.cur_mod_id

        rel = node.relative
        if self.cur_mod_node.is_package_init_file():
            rel -= 1
        if len(parts) < rel:
            self.fail("Relative import climbs too many namespaces", node)
        if rel != 0:
            cur_mod_id = ".".join(parts[:-rel])

        return cur_mod_id + (("." + node.id) if node.id else "")

    def visit_import_all(self, i: ImportAll) -> None:
        i_id = self.correct_relative_import(i)
        if i_id in self.modules:
            m = self.modules[i_id]
            self.add_submodules_to_parent_modules(i_id, True)
            for name, node in m.names.items():
                node = self.normalize_type_alias(node, i)
                if not name.startswith('_') and node.module_public:
                    existing_symbol = self.globals.get(name)
                    if existing_symbol:
                        # Import can redefine a variable. They get special treatment.
                        if self.process_import_over_existing_name(
                                name, existing_symbol, node, i):
                            continue
                    self.add_symbol(name, SymbolTableNode(node.kind, node.node,
                                                          self.cur_mod_id,
                                                          node.type_override,
                                                          normalized=node.normalized), i)
        else:
            # Don't add any dummy symbols for 'from x import *' if 'x' is unknown.
            pass

    def add_unknown_symbol(self, name: str, context: Context, is_import: bool = False) -> None:
        var = Var(name)
        if self.type:
            var._fullname = self.type.fullname() + "." + name
        else:
            var._fullname = self.qualified_name(name)
        var.is_ready = True
        var.type = AnyType()
        var.is_suppressed_import = is_import
        self.add_symbol(name, SymbolTableNode(GDEF, var, self.cur_mod_id), context)

    #
    # Statements
    #

    def visit_block(self, b: Block) -> None:
        if b.is_unreachable:
            return
        self.block_depth[-1] += 1
        for s in b.body:
            self.accept(s)
        self.block_depth[-1] -= 1

    def visit_block_maybe(self, b: Block) -> None:
        if b:
            self.visit_block(b)

    def anal_type(self, t: Type, allow_tuple_literal: bool = False,
                  aliasing: bool = False) -> Type:
        if t:
            a = TypeAnalyser(self.lookup_qualified,
                             self.lookup_fully_qualified,
                             self.fail,
                             aliasing=aliasing,
                             allow_tuple_literal=allow_tuple_literal,
                             allow_unnormalized=self.is_stub_file)
            return t.accept(a)
        else:
            return None

    def visit_assignment_stmt(self, s: AssignmentStmt) -> None:
        for lval in s.lvalues:
            self.analyze_lvalue(lval, explicit_type=s.type is not None)
        self.check_classvar(s)
        s.rvalue.accept(self)
        if s.type:
            allow_tuple_literal = isinstance(s.lvalues[-1], (TupleExpr, ListExpr))
            s.type = self.anal_type(s.type, allow_tuple_literal)
        else:
            # For simple assignments, allow binding type aliases.
            # Also set the type if the rvalue is a simple literal.
            if (s.type is None and len(s.lvalues) == 1 and
                    isinstance(s.lvalues[0], NameExpr)):
                if s.lvalues[0].is_def:
                    s.type = self.analyze_simple_literal_type(s.rvalue)
                res = analyze_type_alias(s.rvalue,
                                         self.lookup_qualified,
                                         self.lookup_fully_qualified,
                                         self.fail, allow_unnormalized=True)
                if res and (not isinstance(res, Instance) or res.args):
                    # TODO: What if this gets reassigned?
                    name = s.lvalues[0]
                    node = self.lookup(name.name, name)
                    node.kind = TYPE_ALIAS
                    node.type_override = res
                    if isinstance(s.rvalue, IndexExpr):
                        s.rvalue.analyzed = TypeAliasExpr(res,
                                                          fallback=self.alias_fallback(res))
        if s.type:
            # Store type into nodes.
            for lvalue in s.lvalues:
                self.store_declared_types(lvalue, s.type)
        self.check_and_set_up_type_alias(s)
        self.process_newtype_declaration(s)
        self.process_typevar_declaration(s)
        self.process_namedtuple_definition(s)
        self.process_typeddict_definition(s)
        self.process_enum_call(s)

        if (len(s.lvalues) == 1 and isinstance(s.lvalues[0], NameExpr) and
                s.lvalues[0].name == '__all__' and s.lvalues[0].kind == GDEF and
                isinstance(s.rvalue, (ListExpr, TupleExpr))):
            self.add_exports(*s.rvalue.items)

    def analyze_simple_literal_type(self, rvalue: Expression) -> Optional[Type]:
        """Return builtins.int if rvalue is an int literal, etc."""
        if self.options.semantic_analysis_only or self.function_stack:
            # Skip this if we're only doing the semantic analysis pass.
            # This is mostly to avoid breaking unit tests.
            # Also skip inside a function; this is to avoid confusing
            # the code that handles dead code due to isinstance()
            # inside type variables with value restrictions (like
            # AnyStr).
            return None
        if isinstance(rvalue, IntExpr):
            return self.named_type_or_none('builtins.int')
        if isinstance(rvalue, FloatExpr):
            return self.named_type_or_none('builtins.float')
        if isinstance(rvalue, StrExpr):
            return self.named_type_or_none('builtins.str')
        if isinstance(rvalue, BytesExpr):
            return self.named_type_or_none('builtins.bytes')
        if isinstance(rvalue, UnicodeExpr):
            return self.named_type_or_none('builtins.unicode')
        return None

    def alias_fallback(self, tp: Type) -> Instance:
        """Make a dummy Instance with no methods. It is used as a fallback type
        to detect errors for non-Instance aliases (i.e. Unions, Tuples, Callables).
        """
        kind = (' to Callable' if isinstance(tp, CallableType) else
                ' to Tuple' if isinstance(tp, TupleType) else
                ' to Union' if isinstance(tp, UnionType) else '')
        cdef = ClassDef('Type alias' + kind, Block([]))
        fb_info = TypeInfo(SymbolTable(), cdef, self.cur_mod_id)
        fb_info.bases = [self.object_type()]
        fb_info.mro = [fb_info, self.object_type().type]
        return Instance(fb_info, [])

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
                        sym = self.lookup_type_node(rvalue)
                        if sym:
                            self.globals[lvalue.name] = sym

    def analyze_lvalue(self, lval: Lvalue, nested: bool = False,
                       add_global: bool = False,
                       explicit_type: bool = False) -> None:
        """Analyze an lvalue or assignment target.

        Only if add_global is True, add name to globals table. If nested
        is true, the lvalue is within a tuple or list lvalue expression.
        """

        if isinstance(lval, NameExpr):
            # Top-level definitions within some statements (at least while) are
            # not handled in the first pass, so they have to be added now.
            nested_global = (not self.is_func_scope() and
                             self.block_depth[-1] > 0 and
                             not self.type)
            if (add_global or nested_global) and lval.name not in self.globals:
                # Define new global name.
                v = Var(lval.name)
                v.set_line(lval)
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
                assert lval.node.name() in self.globals
            elif (self.is_func_scope() and lval.name not in self.locals[-1] and
                  lval.name not in self.global_decls[-1] and
                  lval.name not in self.nonlocal_decls[-1]):
                # Define new local name.
                v = Var(lval.name)
                v.set_line(lval)
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
                v.set_line(lval)
                lval.node = v
                lval.is_def = True
                lval.kind = MDEF
                lval.fullname = lval.name
                self.type.names[lval.name] = SymbolTableNode(MDEF, v)
            elif explicit_type:
                # Don't re-bind types
                self.name_already_defined(lval.name, lval)
            else:
                # Bind to an existing name.
                lval.accept(self)
                self.check_lvalue_validity(lval.node, lval)
        elif isinstance(lval, MemberExpr):
            if not add_global:
                self.analyze_member_lvalue(lval)
            if explicit_type and not self.is_self_member_ref(lval):
                self.fail('Type cannot be declared in assignment to non-self '
                          'attribute', lval)
        elif isinstance(lval, IndexExpr):
            if explicit_type:
                self.fail('Unexpected type declaration', lval)
            if not add_global:
                lval.accept(self)
        elif (isinstance(lval, TupleExpr) or
              isinstance(lval, ListExpr)):
            items = lval.items
            if len(items) == 0 and isinstance(lval, TupleExpr):
                self.fail("can't assign to ()", lval)
            self.analyze_tuple_or_list_lvalue(lval, add_global, explicit_type)
        elif isinstance(lval, StarExpr):
            if nested:
                self.analyze_lvalue(lval.expr, nested, add_global, explicit_type)
            else:
                self.fail('Starred assignment target must be in a list or tuple', lval)
        else:
            self.fail('Invalid assignment target', lval)

    def analyze_tuple_or_list_lvalue(self, lval: Union[ListExpr, TupleExpr],
                                     add_global: bool = False,
                                     explicit_type: bool = False) -> None:
        """Analyze an lvalue or assignment target that is a list or tuple."""
        items = lval.items
        star_exprs = [item for item in items if isinstance(item, StarExpr)]

        if len(star_exprs) > 1:
            self.fail('Two starred expressions in assignment', lval)
        else:
            if len(star_exprs) == 1:
                star_exprs[0].valid = True
            for i in items:
                self.analyze_lvalue(i, nested=True, add_global=add_global,
                                    explicit_type = explicit_type)

    def analyze_member_lvalue(self, lval: MemberExpr) -> None:
        lval.accept(self)
        if (self.is_self_member_ref(lval) and
                self.type.get(lval.name) is None):
            # Implicit attribute definition in __init__.
            lval.is_def = True
            v = Var(lval.name)
            v.set_line(lval)
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
        node = memberexpr.expr.node
        return isinstance(node, Var) and node.is_self

    def check_lvalue_validity(self, node: Union[Expression, SymbolNode], ctx: Context) -> None:
        if isinstance(node, TypeVarExpr):
            self.fail('Invalid assignment target', ctx)
        elif isinstance(node, TypeInfo):
            self.fail(CANNOT_ASSIGN_TO_TYPE, ctx)

    def store_declared_types(self, lvalue: Lvalue, typ: Type) -> None:
        if isinstance(typ, StarType) and not isinstance(lvalue, StarExpr):
            self.fail('Star type only allowed for starred expressions', lvalue)
        if isinstance(lvalue, RefExpr):
            lvalue.is_def = False
            if isinstance(lvalue.node, Var):
                var = lvalue.node
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
        elif isinstance(lvalue, StarExpr):
            # Historical behavior for the old parser
            if isinstance(typ, StarType):
                self.store_declared_types(lvalue.expr, typ.type)
            else:
                self.store_declared_types(lvalue.expr, typ)
        else:
            # This has been flagged elsewhere as an error, so just ignore here.
            pass

    def process_newtype_declaration(self, s: AssignmentStmt) -> None:
        """Check if s declares a NewType; if yes, store it in symbol table."""
        # Extract and check all information from newtype declaration
        name, call = self.analyze_newtype_declaration(s)
        if name is None or call is None:
            return

        old_type = self.check_newtype_args(name, call, s)
        call.analyzed = NewTypeExpr(name, old_type, line=call.line)
        if old_type is None:
            return

        # Create the corresponding class definition if the aliased type is subtypeable
        if isinstance(old_type, TupleType):
            newtype_class_info = self.build_newtype_typeinfo(name, old_type, old_type.fallback)
            newtype_class_info.tuple_type = old_type
        elif isinstance(old_type, Instance):
            newtype_class_info = self.build_newtype_typeinfo(name, old_type, old_type)
        else:
            message = "Argument 2 to NewType(...) must be subclassable (got {})"
            self.fail(message.format(old_type), s)
            return

        # If so, add it to the symbol table.
        node = self.lookup(name, s)
        if node is None:
            self.fail("Could not find {} in current namespace".format(name), s)
            return
        # TODO: why does NewType work in local scopes despite always being of kind GDEF?
        node.kind = GDEF
        call.analyzed.info = node.node = newtype_class_info

    def analyze_newtype_declaration(self,
            s: AssignmentStmt) -> Tuple[Optional[str], Optional[CallExpr]]:
        """Return the NewType call expression if `s` is a newtype declaration or None otherwise."""
        name, call = None, None
        if (len(s.lvalues) == 1
                and isinstance(s.lvalues[0], NameExpr)
                and isinstance(s.rvalue, CallExpr)
                and isinstance(s.rvalue.callee, RefExpr)
                and s.rvalue.callee.fullname == 'typing.NewType'):
            lvalue = s.lvalues[0]
            name = s.lvalues[0].name
            if not lvalue.is_def:
                if s.type:
                    self.fail("Cannot declare the type of a NewType declaration", s)
                else:
                    self.fail("Cannot redefine '%s' as a NewType" % name, s)

            # This dummy NewTypeExpr marks the call as sufficiently analyzed; it will be
            # overwritten later with a fully complete NewTypeExpr if there are no other
            # errors with the NewType() call.
            call = s.rvalue

        return name, call

    def check_newtype_args(self, name: str, call: CallExpr, context: Context) -> Optional[Type]:
        has_failed = False
        args, arg_kinds = call.args, call.arg_kinds
        if len(args) != 2 or arg_kinds[0] != ARG_POS or arg_kinds[1] != ARG_POS:
            self.fail("NewType(...) expects exactly two positional arguments", context)
            return None

        # Check first argument
        if not isinstance(args[0], (StrExpr, BytesExpr, UnicodeExpr)):
            self.fail("Argument 1 to NewType(...) must be a string literal", context)
            has_failed = True
        elif args[0].value != name:
            msg = "String argument 1 '{}' to NewType(...) does not match variable name '{}'"
            self.fail(msg.format(args[0].value, name), context)
            has_failed = True

        # Check second argument
        try:
            unanalyzed_type = expr_to_unanalyzed_type(args[1])
        except TypeTranslationError:
            self.fail("Argument 2 to NewType(...) must be a valid type", context)
            return None
        old_type = self.anal_type(unanalyzed_type)

        if isinstance(old_type, Instance) and old_type.type.is_newtype:
            self.fail("Argument 2 to NewType(...) cannot be another NewType", context)
            has_failed = True

        return None if has_failed else old_type

    def build_newtype_typeinfo(self, name: str, old_type: Type, base_type: Instance) -> TypeInfo:
        info = self.basic_new_typeinfo(name, base_type)
        info.is_newtype = True

        # Add __init__ method
        args = [Argument(Var('cls'), NoneTyp(), None, ARG_POS),
                self.make_argument('item', old_type)]
        signature = CallableType(
            arg_types=[cast(Type, None), old_type],
            arg_kinds=[arg.kind for arg in args],
            arg_names=['self', 'item'],
            ret_type=old_type,
            fallback=self.named_type('__builtins__.function'),
            name=name)
        init_func = FuncDef('__init__', args, Block([]), typ=signature)
        init_func.info = info
        info.names['__init__'] = SymbolTableNode(MDEF, init_func)

        return info

    def process_typevar_declaration(self, s: AssignmentStmt) -> None:
        """Check if s declares a TypeVar; it yes, store it in symbol table."""
        call = self.get_typevar_declaration(s)
        if not call:
            return

        lvalue = s.lvalues[0]
        assert isinstance(lvalue, NameExpr)
        name = lvalue.name
        if not lvalue.is_def:
            if s.type:
                self.fail("Cannot declare the type of a type variable", s)
            else:
                self.fail("Cannot redefine '%s' as a type variable" % name, s)
            return

        if not self.check_typevar_name(call, name, s):
            return

        # Constraining types
        n_values = call.arg_kinds[1:].count(ARG_POS)
        values = self.analyze_types(call.args[1:1 + n_values])

        res = self.process_typevar_parameters(call.args[1 + n_values:],
                                              call.arg_names[1 + n_values:],
                                              call.arg_kinds[1 + n_values:],
                                              n_values,
                                              s)
        if res is None:
            return
        variance, upper_bound = res

        # Yes, it's a valid type variable definition! Add it to the symbol table.
        node = self.lookup(name, s)
        node.kind = UNBOUND_TVAR
        TypeVar = TypeVarExpr(name, node.fullname, values, upper_bound, variance)
        TypeVar.line = call.line
        call.analyzed = TypeVar
        node.node = TypeVar

    def check_typevar_name(self, call: CallExpr, name: str, context: Context) -> bool:
        if len(call.args) < 1:
            self.fail("Too few arguments for TypeVar()", context)
            return False
        if (not isinstance(call.args[0], (StrExpr, BytesExpr, UnicodeExpr))
                or not call.arg_kinds[0] == ARG_POS):
            self.fail("TypeVar() expects a string literal as first argument", context)
            return False
        elif call.args[0].value != name:
            msg = "String argument 1 '{}' to TypeVar(...) does not match variable name '{}'"
            self.fail(msg.format(call.args[0].value, name), context)
            return False
        return True

    def get_typevar_declaration(self, s: AssignmentStmt) -> Optional[CallExpr]:
        """Returns the TypeVar() call expression if `s` is a type var declaration
        or None otherwise.
        """
        if len(s.lvalues) != 1 or not isinstance(s.lvalues[0], NameExpr):
            return None
        if not isinstance(s.rvalue, CallExpr):
            return None
        call = s.rvalue
        callee = call.callee
        if not isinstance(callee, RefExpr):
            return None
        if callee.fullname != 'typing.TypeVar':
            return None
        return call

    def process_typevar_parameters(self, args: List[Expression],
                                   names: List[Optional[str]],
                                   kinds: List[int],
                                   num_values: int,
                                   context: Context) -> Optional[Tuple[int, Type]]:
        has_values = (num_values > 0)
        covariant = False
        contravariant = False
        upper_bound = self.object_type()   # type: Type
        for param_value, param_name, param_kind in zip(args, names, kinds):
            if not param_kind == ARG_NAMED:
                self.fail("Unexpected argument to TypeVar()", context)
                return None
            if param_name == 'covariant':
                if isinstance(param_value, NameExpr):
                    if param_value.name == 'True':
                        covariant = True
                    else:
                        self.fail("TypeVar 'covariant' may only be 'True'", context)
                        return None
                else:
                    self.fail("TypeVar 'covariant' may only be 'True'", context)
                    return None
            elif param_name == 'contravariant':
                if isinstance(param_value, NameExpr):
                    if param_value.name == 'True':
                        contravariant = True
                    else:
                        self.fail("TypeVar 'contravariant' may only be 'True'", context)
                        return None
                else:
                    self.fail("TypeVar 'contravariant' may only be 'True'", context)
                    return None
            elif param_name == 'bound':
                if has_values:
                    self.fail("TypeVar cannot have both values and an upper bound", context)
                    return None
                try:
                    upper_bound = self.expr_to_analyzed_type(param_value)
                except TypeTranslationError:
                    self.fail("TypeVar 'bound' must be a type", param_value)
                    return None
            elif param_name == 'values':
                # Probably using obsolete syntax with values=(...). Explain the current syntax.
                self.fail("TypeVar 'values' argument not supported", context)
                self.fail("Use TypeVar('T', t, ...) instead of TypeVar('T', values=(t, ...))",
                          context)
                return None
            else:
                self.fail("Unexpected argument to TypeVar(): {}".format(param_name), context)
                return None

        if covariant and contravariant:
            self.fail("TypeVar cannot be both covariant and contravariant", context)
            return None
        elif num_values == 1:
            self.fail("TypeVar cannot have only a single constraint", context)
            return None
        elif covariant:
            variance = COVARIANT
        elif contravariant:
            variance = CONTRAVARIANT
        else:
            variance = INVARIANT
        return (variance, upper_bound)

    def process_namedtuple_definition(self, s: AssignmentStmt) -> None:
        """Check if s defines a namedtuple; if yes, store the definition in symbol table."""
        if len(s.lvalues) != 1 or not isinstance(s.lvalues[0], NameExpr):
            return
        lvalue = s.lvalues[0]
        name = lvalue.name
        named_tuple = self.check_namedtuple(s.rvalue, name)
        if named_tuple is None:
            return
        # Yes, it's a valid namedtuple definition. Add it to the symbol table.
        node = self.lookup(name, s)
        node.kind = GDEF   # TODO locally defined namedtuple
        node.node = named_tuple

    def check_namedtuple(self, node: Expression, var_name: str = None) -> Optional[TypeInfo]:
        """Check if a call defines a namedtuple.

        The optional var_name argument is the name of the variable to
        which this is assigned, if any.

        If it does, return the corresponding TypeInfo. Return None otherwise.

        If the definition is invalid but looks like a namedtuple,
        report errors but return (some) TypeInfo.
        """
        if not isinstance(node, CallExpr):
            return None
        call = node
        callee = call.callee
        if not isinstance(callee, RefExpr):
            return None
        fullname = callee.fullname
        if fullname not in ('collections.namedtuple', 'typing.NamedTuple'):
            return None
        items, types, ok = self.parse_namedtuple_args(call, fullname)
        if not ok:
            # Error. Construct dummy return value.
            return self.build_namedtuple_typeinfo('namedtuple', [], [], {})
        name = cast(StrExpr, call.args[0]).value
        if name != var_name or self.is_func_scope():
            # Give it a unique name derived from the line number.
            name += '@' + str(call.line)
        info = self.build_namedtuple_typeinfo(name, items, types, {})
        # Store it as a global just in case it would remain anonymous.
        # (Or in the nearest class if there is one.)
        stnode = SymbolTableNode(GDEF, info, self.cur_mod_id)
        if self.type:
            self.type.names[name] = stnode
        else:
            self.globals[name] = stnode
        call.analyzed = NamedTupleExpr(info)
        call.analyzed.set_line(call.line, call.column)
        return info

    def parse_namedtuple_args(self, call: CallExpr,
                              fullname: str) -> Tuple[List[str], List[Type], bool]:
        # TODO: Share code with check_argument_count in checkexpr.py?
        args = call.args
        if len(args) < 2:
            return self.fail_namedtuple_arg("Too few arguments for namedtuple()", call)
        if len(args) > 2:
            # FIX incorrect. There are two additional parameters
            return self.fail_namedtuple_arg("Too many arguments for namedtuple()", call)
        if call.arg_kinds != [ARG_POS, ARG_POS]:
            return self.fail_namedtuple_arg("Unexpected arguments to namedtuple()", call)
        if not isinstance(args[0], (StrExpr, BytesExpr, UnicodeExpr)):
            return self.fail_namedtuple_arg(
                "namedtuple() expects a string literal as the first argument", call)
        types = []  # type: List[Type]
        ok = True
        if not isinstance(args[1], (ListExpr, TupleExpr)):
            if (fullname == 'collections.namedtuple'
                    and isinstance(args[1], (StrExpr, BytesExpr, UnicodeExpr))):
                str_expr = cast(StrExpr, args[1])
                items = str_expr.value.replace(',', ' ').split()
            else:
                return self.fail_namedtuple_arg(
                    "List or tuple literal expected as the second argument to namedtuple()", call)
        else:
            listexpr = args[1]
            if fullname == 'collections.namedtuple':
                # The fields argument contains just names, with implicit Any types.
                if any(not isinstance(item, (StrExpr, BytesExpr, UnicodeExpr))
                       for item in listexpr.items):
                    return self.fail_namedtuple_arg("String literal expected as namedtuple() item",
                                                    call)
                items = [cast(StrExpr, item).value for item in listexpr.items]
            else:
                # The fields argument contains (name, type) tuples.
                items, types, ok = self.parse_namedtuple_fields_with_types(listexpr.items, call)
        if not types:
            types = [AnyType() for _ in items]
        underscore = [item for item in items if item.startswith('_')]
        if underscore:
            self.fail("namedtuple() field names cannot start with an underscore: "
                      + ', '.join(underscore), call)
        return items, types, ok

    def parse_namedtuple_fields_with_types(self, nodes: List[Expression],
                                           context: Context) -> Tuple[List[str], List[Type], bool]:
        items = []  # type: List[str]
        types = []  # type: List[Type]
        for item in nodes:
            if isinstance(item, TupleExpr):
                if len(item.items) != 2:
                    return self.fail_namedtuple_arg("Invalid NamedTuple field definition",
                                                    item)
                name, type_node = item.items
                if isinstance(name, (StrExpr, BytesExpr, UnicodeExpr)):
                    items.append(name.value)
                else:
                    return self.fail_namedtuple_arg("Invalid NamedTuple() field name", item)
                try:
                    type = expr_to_unanalyzed_type(type_node)
                except TypeTranslationError:
                    return self.fail_namedtuple_arg('Invalid field type', type_node)
                types.append(self.anal_type(type))
            else:
                return self.fail_namedtuple_arg("Tuple expected as NamedTuple() field", item)
        return items, types, True

    def fail_namedtuple_arg(self, message: str,
                            context: Context) -> Tuple[List[str], List[Type], bool]:
        self.fail(message, context)
        return [], [], False

    def basic_new_typeinfo(self, name: str, basetype_or_fallback: Instance) -> TypeInfo:
        class_def = ClassDef(name, Block([]))
        class_def.fullname = self.qualified_name(name)

        info = TypeInfo(SymbolTable(), class_def, self.cur_mod_id)
        info.mro = [info] + basetype_or_fallback.type.mro
        info.bases = [basetype_or_fallback]
        return info

    def build_namedtuple_typeinfo(self, name: str, items: List[str], types: List[Type],
                                  default_items: Dict[str, Expression]) -> TypeInfo:
        strtype = self.str_type()
        basetuple_type = self.named_type('__builtins__.tuple', [AnyType()])
        dictype = (self.named_type_or_none('builtins.dict', [strtype, AnyType()])
                   or self.object_type())
        # Actual signature should return OrderedDict[str, Union[types]]
        ordereddictype = (self.named_type_or_none('builtins.dict', [strtype, AnyType()])
                          or self.object_type())
        fallback = self.named_type('__builtins__.tuple', [join.join_type_list(types)])
        # Note: actual signature should accept an invariant version of Iterable[UnionType[types]].
        # but it can't be expressed. 'new' and 'len' should be callable types.
        iterable_type = self.named_type_or_none('typing.Iterable', [AnyType()])
        function_type = self.named_type('__builtins__.function')

        info = self.basic_new_typeinfo(name, fallback)
        info.is_named_tuple = True
        info.tuple_type = TupleType(types, fallback)

        def add_field(var: Var, is_initialized_in_class: bool = False,
                      is_property: bool = False) -> None:
            var.info = info
            var.is_initialized_in_class = is_initialized_in_class
            var.is_property = is_property
            info.names[var.name()] = SymbolTableNode(MDEF, var)

        vars = [Var(item, typ) for item, typ in zip(items, types)]
        for var in vars:
            add_field(var, is_property=True)

        tuple_of_strings = TupleType([strtype for _ in items], basetuple_type)
        add_field(Var('_fields', tuple_of_strings), is_initialized_in_class=True)
        add_field(Var('_field_types', dictype), is_initialized_in_class=True)
        add_field(Var('_field_defaults', dictype), is_initialized_in_class=True)
        add_field(Var('_source', strtype), is_initialized_in_class=True)

        tvd = TypeVarDef('NT', 1, [], info.tuple_type)
        selftype = TypeVarType(tvd)

        def add_method(funcname: str,
                       ret: Type,
                       args: List[Argument],
                       name: str = None,
                       is_classmethod: bool = False,
                       ) -> None:
            if is_classmethod:
                first = [Argument(Var('cls'), TypeType(selftype), None, ARG_POS)]
            else:
                first = [Argument(Var('self'), selftype, None, ARG_POS)]
            args = first + args

            types = [arg.type_annotation for arg in args]
            items = [arg.variable.name() for arg in args]
            arg_kinds = [arg.kind for arg in args]
            signature = CallableType(types, arg_kinds, items, ret, function_type,
                                     name=name or info.name() + '.' + funcname)
            signature.variables = [tvd]
            func = FuncDef(funcname, args, Block([]), typ=signature)
            func.info = info
            func.is_class = is_classmethod
            if is_classmethod:
                v = Var(funcname, signature)
                v.is_classmethod = True
                v.info = info
                dec = Decorator(func, [NameExpr('classmethod')], v)
                info.names[funcname] = SymbolTableNode(MDEF, dec)
            else:
                info.names[funcname] = SymbolTableNode(MDEF, func)

        add_method('_replace', ret=selftype,
                   args=[Argument(var, var.type, EllipsisExpr(), ARG_NAMED_OPT) for var in vars])

        def make_init_arg(var: Var) -> Argument:
            default = default_items.get(var.name(), None)
            kind = ARG_POS if default is None else ARG_OPT
            return Argument(var, var.type, default, kind)

        add_method('__init__', ret=NoneTyp(), name=info.name(),
                   args=[make_init_arg(var) for var in vars])
        add_method('_asdict', args=[], ret=ordereddictype)
        add_method('_make', ret=selftype, is_classmethod=True,
                   args=[Argument(Var('iterable', iterable_type), iterable_type, None, ARG_POS),
                         Argument(Var('new'), AnyType(), EllipsisExpr(), ARG_NAMED_OPT),
                         Argument(Var('len'), AnyType(), EllipsisExpr(), ARG_NAMED_OPT)])
        return info

    def make_argument(self, name: str, type: Type) -> Argument:
        return Argument(Var(name), type, None, ARG_POS)

    def analyze_types(self, items: List[Expression]) -> List[Type]:
        result = []  # type: List[Type]
        for node in items:
            try:
                result.append(self.anal_type(expr_to_unanalyzed_type(node)))
            except TypeTranslationError:
                self.fail('Type expected', node)
                result.append(AnyType())
        return result

    def process_typeddict_definition(self, s: AssignmentStmt) -> None:
        """Check if s defines a TypedDict; if yes, store the definition in symbol table."""
        if len(s.lvalues) != 1 or not isinstance(s.lvalues[0], NameExpr):
            return
        lvalue = s.lvalues[0]
        name = lvalue.name
        typed_dict = self.check_typeddict(s.rvalue, name)
        if typed_dict is None:
            return
        # Yes, it's a valid TypedDict definition. Add it to the symbol table.
        node = self.lookup(name, s)
        if node:
            node.kind = GDEF   # TODO locally defined TypedDict
            node.node = typed_dict

    def check_typeddict(self, node: Expression, var_name: str = None) -> Optional[TypeInfo]:
        """Check if a call defines a TypedDict.

        The optional var_name argument is the name of the variable to
        which this is assigned, if any.

        If it does, return the corresponding TypeInfo. Return None otherwise.

        If the definition is invalid but looks like a TypedDict,
        report errors but return (some) TypeInfo.
        """
        if not isinstance(node, CallExpr):
            return None
        call = node
        callee = call.callee
        if not isinstance(callee, RefExpr):
            return None
        fullname = callee.fullname
        if fullname != 'mypy_extensions.TypedDict':
            return None
        items, types, ok = self.parse_typeddict_args(call, fullname)
        if not ok:
            # Error. Construct dummy return value.
            return self.build_typeddict_typeinfo('TypedDict', [], [])
        name = cast(StrExpr, call.args[0]).value
        if name != var_name or self.is_func_scope():
            # Give it a unique name derived from the line number.
            name += '@' + str(call.line)
        info = self.build_typeddict_typeinfo(name, items, types)
        # Store it as a global just in case it would remain anonymous.
        # (Or in the nearest class if there is one.)
        stnode = SymbolTableNode(GDEF, info, self.cur_mod_id)
        if self.type:
            self.type.names[name] = stnode
        else:
            self.globals[name] = stnode
        call.analyzed = TypedDictExpr(info)
        call.analyzed.set_line(call.line, call.column)
        return info

    def parse_typeddict_args(self, call: CallExpr,
                             fullname: str) -> Tuple[List[str], List[Type], bool]:
        # TODO: Share code with check_argument_count in checkexpr.py?
        args = call.args
        if len(args) < 2:
            return self.fail_typeddict_arg("Too few arguments for TypedDict()", call)
        if len(args) > 2:
            return self.fail_typeddict_arg("Too many arguments for TypedDict()", call)
        # TODO: Support keyword arguments
        if call.arg_kinds != [ARG_POS, ARG_POS]:
            return self.fail_typeddict_arg("Unexpected arguments to TypedDict()", call)
        if not isinstance(args[0], (StrExpr, BytesExpr, UnicodeExpr)):
            return self.fail_typeddict_arg(
                "TypedDict() expects a string literal as the first argument", call)
        if not isinstance(args[1], DictExpr):
            return self.fail_typeddict_arg(
                "TypedDict() expects a dictionary literal as the second argument", call)
        dictexpr = args[1]
        items, types, ok = self.parse_typeddict_fields_with_types(dictexpr.items, call)
        return items, types, ok

    def parse_typeddict_fields_with_types(self, dict_items: List[Tuple[Expression, Expression]],
                                          context: Context) -> Tuple[List[str], List[Type], bool]:
        items = []  # type: List[str]
        types = []  # type: List[Type]
        for (field_name_expr, field_type_expr) in dict_items:
            if isinstance(field_name_expr, (StrExpr, BytesExpr, UnicodeExpr)):
                items.append(field_name_expr.value)
            else:
                return self.fail_typeddict_arg("Invalid TypedDict() field name", field_name_expr)
            try:
                type = expr_to_unanalyzed_type(field_type_expr)
            except TypeTranslationError:
                return self.fail_typeddict_arg('Invalid field type', field_type_expr)
            types.append(self.anal_type(type))
        return items, types, True

    def fail_typeddict_arg(self, message: str,
                           context: Context) -> Tuple[List[str], List[Type], bool]:
        self.fail(message, context)
        return [], [], False

    def build_typeddict_typeinfo(self, name: str, items: List[str],
                                 types: List[Type]) -> TypeInfo:
        mapping_value_type = join.join_type_list(types)
        fallback = (self.named_type_or_none('typing.Mapping',
                                            [self.str_type(), mapping_value_type])
                    or self.object_type())

        info = self.basic_new_typeinfo(name, fallback)
        info.typeddict_type = TypedDictType(OrderedDict(zip(items, types)), fallback)

        return info

    def check_classvar(self, s: AssignmentStmt) -> None:
        lvalue = s.lvalues[0]
        if len(s.lvalues) != 1 or not isinstance(lvalue, RefExpr):
            return
        if not self.is_classvar(s.type):
            return
        if self.is_class_scope() and isinstance(lvalue, NameExpr):
            node = lvalue.node
            if isinstance(node, Var):
                node.is_classvar = True
        elif not isinstance(lvalue, MemberExpr) or self.is_self_member_ref(lvalue):
            # In case of member access, report error only when assigning to self
            # Other kinds of member assignments should be already reported
            self.fail_invalid_classvar(lvalue)

    def is_classvar(self, typ: Type) -> bool:
        if not isinstance(typ, UnboundType):
            return False
        sym = self.lookup_qualified(typ.name, typ)
        if not sym or not sym.node:
            return False
        return sym.node.fullname() == 'typing.ClassVar'

    def fail_invalid_classvar(self, context: Context) -> None:
        self.fail('ClassVar can only be used for assignments in class body', context)

    def process_enum_call(self, s: AssignmentStmt) -> None:
        """Check if s defines an Enum; if yes, store the definition in symbol table."""
        if len(s.lvalues) != 1 or not isinstance(s.lvalues[0], NameExpr):
            return
        lvalue = s.lvalues[0]
        name = lvalue.name
        enum_call = self.check_enum_call(s.rvalue, name)
        if enum_call is None:
            return
        # Yes, it's a valid Enum definition. Add it to the symbol table.
        node = self.lookup(name, s)
        if node:
            node.kind = GDEF   # TODO locally defined Enum
            node.node = enum_call

    def check_enum_call(self, node: Expression, var_name: str = None) -> Optional[TypeInfo]:
        """Check if a call defines an Enum.

        Example:

          A = enum.Enum('A', 'foo bar')

        is equivalent to:

          class A(enum.Enum):
              foo = 1
              bar = 2
        """
        if not isinstance(node, CallExpr):
            return None
        call = node
        callee = call.callee
        if not isinstance(callee, RefExpr):
            return None
        fullname = callee.fullname
        if fullname not in ('enum.Enum', 'enum.IntEnum', 'enum.Flag', 'enum.IntFlag'):
            return None
        items, values, ok = self.parse_enum_call_args(call, fullname.split('.')[-1])
        if not ok:
            # Error. Construct dummy return value.
            return self.build_enum_call_typeinfo('Enum', [], fullname)
        name = cast(StrExpr, call.args[0]).value
        if name != var_name or self.is_func_scope():
            # Give it a unique name derived from the line number.
            name += '@' + str(call.line)
        info = self.build_enum_call_typeinfo(name, items, fullname)
        # Store it as a global just in case it would remain anonymous.
        # (Or in the nearest class if there is one.)
        stnode = SymbolTableNode(GDEF, info, self.cur_mod_id)
        if self.type:
            self.type.names[name] = stnode
        else:
            self.globals[name] = stnode
        call.analyzed = EnumCallExpr(info, items, values)
        call.analyzed.set_line(call.line, call.column)
        return info

    def build_enum_call_typeinfo(self, name: str, items: List[str], fullname: str) -> TypeInfo:
        base = self.named_type_or_none(fullname)
        assert base is not None
        info = self.basic_new_typeinfo(name, base)
        info.is_enum = True
        for item in items:
            var = Var(item)
            var.info = info
            var.is_property = True
            info.names[item] = SymbolTableNode(MDEF, var)
        return info

    def parse_enum_call_args(self, call: CallExpr,
                             class_name: str) -> Tuple[List[str],
                                                       List[Optional[Expression]], bool]:
        args = call.args
        if len(args) < 2:
            return self.fail_enum_call_arg("Too few arguments for %s()" % class_name, call)
        if len(args) > 2:
            return self.fail_enum_call_arg("Too many arguments for %s()" % class_name, call)
        if call.arg_kinds != [ARG_POS, ARG_POS]:
            return self.fail_enum_call_arg("Unexpected arguments to %s()" % class_name, call)
        if not isinstance(args[0], (StrExpr, UnicodeExpr)):
            return self.fail_enum_call_arg(
                "%s() expects a string literal as the first argument" % class_name, call)
        items = []
        values = []  # type: List[Optional[Expression]]
        if isinstance(args[1], (StrExpr, UnicodeExpr)):
            fields = args[1].value
            for field in fields.replace(',', ' ').split():
                items.append(field)
        elif isinstance(args[1], (TupleExpr, ListExpr)):
            seq_items = args[1].items
            if all(isinstance(seq_item, (StrExpr, UnicodeExpr)) for seq_item in seq_items):
                items = [cast(StrExpr, seq_item).value for seq_item in seq_items]
            elif all(isinstance(seq_item, (TupleExpr, ListExpr))
                     and len(seq_item.items) == 2
                     and isinstance(seq_item.items[0], (StrExpr, UnicodeExpr))
                     for seq_item in seq_items):
                for seq_item in seq_items:
                    assert isinstance(seq_item, (TupleExpr, ListExpr))
                    name, value = seq_item.items
                    assert isinstance(name, (StrExpr, UnicodeExpr))
                    items.append(name.value)
                    values.append(value)
            else:
                return self.fail_enum_call_arg(
                    "%s() with tuple or list expects strings or (name, value) pairs" %
                    class_name,
                    call)
        elif isinstance(args[1], DictExpr):
            for key, value in args[1].items:
                if not isinstance(key, (StrExpr, UnicodeExpr)):
                    return self.fail_enum_call_arg(
                        "%s() with dict literal requires string literals" % class_name, call)
                items.append(key.value)
                values.append(value)
        else:
            # TODO: Allow dict(x=1, y=2) as a substitute for {'x': 1, 'y': 2}?
            return self.fail_enum_call_arg(
                "%s() expects a string, tuple, list or dict literal as the second argument" %
                class_name,
                call)
        if len(items) == 0:
            return self.fail_enum_call_arg("%s() needs at least one item" % class_name, call)
        if not values:
            values = [None] * len(items)
        assert len(items) == len(values)
        return items, values, True

    def fail_enum_call_arg(self, message: str,
                           context: Context) -> Tuple[List[str],
                                                      List[Optional[Expression]], bool]:
        self.fail(message, context)
        return [], [], False

    def visit_decorator(self, dec: Decorator) -> None:
        for d in dec.decorators:
            d.accept(self)
        removed = []  # type: List[int]
        no_type_check = False
        for i, d in enumerate(dec.decorators):
            # A bunch of decorators are special cased here.
            if refers_to_fullname(d, 'abc.abstractmethod'):
                removed.append(i)
                dec.func.is_abstract = True
                self.check_decorated_function_is_method('abstractmethod', dec)
            elif (refers_to_fullname(d, 'asyncio.coroutines.coroutine') or
                  refers_to_fullname(d, 'types.coroutine')):
                removed.append(i)
                dec.func.is_awaitable_coroutine = True
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
            elif (refers_to_fullname(d, 'builtins.property') or
                  refers_to_fullname(d, 'abc.abstractproperty')):
                removed.append(i)
                dec.func.is_property = True
                dec.var.is_property = True
                if refers_to_fullname(d, 'abc.abstractproperty'):
                    dec.func.is_abstract = True
                self.check_decorated_function_is_method('property', dec)
                if len(dec.func.arguments) > 1:
                    self.fail('Too many arguments', dec.func)
            elif refers_to_fullname(d, 'typing.no_type_check'):
                dec.var.type = AnyType()
                dec.type = dec.var.type
                no_type_check = True
        for i in reversed(removed):
            del dec.decorators[i]
        if not dec.is_overload or dec.var.is_property:
            if self.is_func_scope():
                self.add_symbol(dec.var.name(), SymbolTableNode(LDEF, dec),
                                dec)
            elif self.type:
                dec.var.info = self.type
                dec.var.is_initialized_in_class = True
                self.add_symbol(dec.var.name(), SymbolTableNode(MDEF, dec),
                                dec)
        if not no_type_check:
            dec.func.accept(self)
        if dec.decorators and dec.var.is_property:
            self.fail('Decorated property not supported', dec)

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

    def visit_assert_stmt(self, s: AssertStmt) -> None:
        if s.expr:
            s.expr.accept(self)
        if s.msg:
            s.msg.accept(self)

    def visit_operator_assignment_stmt(self,
                                       s: OperatorAssignmentStmt) -> None:
        s.lvalue.accept(self)
        s.rvalue.accept(self)
        if (isinstance(s.lvalue, NameExpr) and s.lvalue.name == '__all__' and
                s.lvalue.kind == GDEF and isinstance(s.rvalue, (ListExpr, TupleExpr))):
            self.add_exports(*s.rvalue.items)

    def visit_while_stmt(self, s: WhileStmt) -> None:
        s.expr.accept(self)
        self.loop_depth += 1
        s.body.accept(self)
        self.loop_depth -= 1
        self.visit_block_maybe(s.else_body)

    def visit_for_stmt(self, s: ForStmt) -> None:
        s.expr.accept(self)

        # Bind index variables and check if they define new names.
        self.analyze_lvalue(s.index, explicit_type=s.index_type is not None)
        if s.index_type:
            if self.is_classvar(s.index_type):
                self.fail_invalid_classvar(s.index)
            allow_tuple_literal = isinstance(s.index, (TupleExpr, ListExpr))
            s.index_type = self.anal_type(s.index_type, allow_tuple_literal)
            self.store_declared_types(s.index, s.index_type)

        self.loop_depth += 1
        self.visit_block(s.body)
        self.loop_depth -= 1

        self.visit_block_maybe(s.else_body)

    def visit_break_stmt(self, s: BreakStmt) -> None:
        if self.loop_depth == 0:
            self.fail("'break' outside loop", s, True, blocker=True)

    def visit_continue_stmt(self, s: ContinueStmt) -> None:
        if self.loop_depth == 0:
            self.fail("'continue' outside loop", s, True, blocker=True)

    def visit_if_stmt(self, s: IfStmt) -> None:
        infer_reachability_of_if_statement(s,
            pyversion=self.options.python_version,
            platform=self.options.platform)
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
                self.analyze_lvalue(var, add_global=add_global)
            handler.accept(visitor)
        if s.else_body:
            s.else_body.accept(visitor)
        if s.finally_body:
            s.finally_body.accept(visitor)

    def visit_with_stmt(self, s: WithStmt) -> None:
        types = []  # type: List[Type]

        if s.target_type:
            actual_targets = [t for t in s.target if t is not None]
            if len(actual_targets) == 0:
                # We have a type for no targets
                self.fail('Invalid type comment', s)
            elif len(actual_targets) == 1:
                # We have one target and one type
                types = [s.target_type]
            elif isinstance(s.target_type, TupleType):
                # We have multiple targets and multiple types
                if len(actual_targets) == len(s.target_type.items):
                    types = s.target_type.items
                else:
                    # But it's the wrong number of items
                    self.fail('Incompatible number of types for `with` targets', s)
            else:
                # We have multiple targets and one type
                self.fail('Multiple types expected for multiple `with` targets', s)

        new_types = []  # type: List[Type]
        for e, n in zip(s.expr, s.target):
            e.accept(self)
            if n:
                self.analyze_lvalue(n, explicit_type=s.target_type is not None)

                # Since we have a target, pop the next type from types
                if types:
                    t = types.pop(0)
                    if self.is_classvar(t):
                        self.fail_invalid_classvar(n)
                    allow_tuple_literal = isinstance(n, (TupleExpr, ListExpr))
                    t = self.anal_type(t, allow_tuple_literal)
                    new_types.append(t)
                    self.store_declared_types(n, t)

        # Reverse the logic above to correctly reassign target_type
        if new_types:
            if len(s.target) == 1:
                s.target_type = new_types[0]
            elif isinstance(s.target_type, TupleType):
                s.target_type = s.target_type.copy_modified(items=new_types)

        self.visit_block(s.body)

    def visit_del_stmt(self, s: DelStmt) -> None:
        s.expr.accept(self)
        if not self.is_valid_del_target(s.expr):
            self.fail('Invalid delete target', s)

    def is_valid_del_target(self, s: Expression) -> bool:
        if isinstance(s, (IndexExpr, NameExpr, MemberExpr)):
            return True
        elif isinstance(s, TupleExpr):
            return all(self.is_valid_del_target(item) for item in s.items)
        else:
            return False

    def visit_global_decl(self, g: GlobalDecl) -> None:
        for name in g.names:
            if name in self.nonlocal_decls[-1]:
                self.fail("Name '{}' is nonlocal and global".format(name), g)
            self.global_decls[-1].add(name)

    def visit_nonlocal_decl(self, d: NonlocalDecl) -> None:
        if not self.is_func_scope():
            self.fail("nonlocal declaration not allowed at module level", d)
        else:
            for name in d.names:
                for table in reversed(self.locals[:-1]):
                    if table is not None and name in table:
                        break
                else:
                    self.fail("No binding for nonlocal '{}' found".format(name), d)

                if self.locals[-1] is not None and name in self.locals[-1]:
                    self.fail("Name '{}' is already defined in local "
                              "scope before nonlocal declaration".format(name), d)

                if name in self.global_decls[-1]:
                    self.fail("Name '{}' is nonlocal and global".format(name), d)
                self.nonlocal_decls[-1].add(name)

    def visit_print_stmt(self, s: PrintStmt) -> None:
        for arg in s.args:
            arg.accept(self)
        if s.target:
            s.target.accept(self)

    def visit_exec_stmt(self, s: ExecStmt) -> None:
        s.expr.accept(self)
        if s.variables1:
            s.variables1.accept(self)
        if s.variables2:
            s.variables2.accept(self)

    #
    # Expressions
    #

    def visit_name_expr(self, expr: NameExpr) -> None:
        n = self.lookup(expr.name, expr)
        if n:
            if n.kind == BOUND_TVAR:
                self.fail("'{}' is a type variable and only valid in type "
                          "context".format(expr.name), expr)
            else:
                expr.kind = n.kind
                expr.node = n.node
                expr.fullname = n.fullname

    def visit_super_expr(self, expr: SuperExpr) -> None:
        if not self.type:
            self.fail('"super" used outside class', expr)
            return
        expr.info = self.type

    def visit_tuple_expr(self, expr: TupleExpr) -> None:
        for item in expr.items:
            if isinstance(item, StarExpr):
                item.valid = True
            item.accept(self)

    def visit_list_expr(self, expr: ListExpr) -> None:
        for item in expr.items:
            if isinstance(item, StarExpr):
                item.valid = True
            item.accept(self)

    def visit_set_expr(self, expr: SetExpr) -> None:
        for item in expr.items:
            if isinstance(item, StarExpr):
                item.valid = True
            item.accept(self)

    def visit_dict_expr(self, expr: DictExpr) -> None:
        for key, value in expr.items:
            if key is not None:
                key.accept(self)
            value.accept(self)

    def visit_star_expr(self, expr: StarExpr) -> None:
        if not expr.valid:
            # XXX TODO Change this error message
            self.fail('Can use starred expression only as assignment target', expr)
        else:
            expr.expr.accept(self)

    def visit_yield_from_expr(self, e: YieldFromExpr) -> None:
        if not self.is_func_scope():  # not sure
            self.fail("'yield from' outside function", e, True, blocker=True)
        else:
            if self.function_stack[-1].is_coroutine:
                self.fail("'yield from' in async function", e, True, blocker=True)
            else:
                self.function_stack[-1].is_generator = True
        if e.expr:
            e.expr.accept(self)

    def visit_call_expr(self, expr: CallExpr) -> None:
        """Analyze a call expression.

        Some call expressions are recognized as special forms, including
        cast(...).
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
            # Piggyback CastExpr object to the CallExpr object; it takes
            # precedence over the CallExpr semantics.
            expr.analyzed = CastExpr(expr.args[1], target)
            expr.analyzed.line = expr.line
            expr.analyzed.accept(self)
        elif refers_to_fullname(expr.callee, 'builtins.reveal_type'):
            if not self.check_fixed_args(expr, 1, 'reveal_type'):
                return
            expr.analyzed = RevealTypeExpr(expr.args[0])
            expr.analyzed.line = expr.line
            expr.analyzed.column = expr.column
            expr.analyzed.accept(self)
        elif refers_to_fullname(expr.callee, 'typing.Any'):
            # Special form Any(...) no longer supported.
            self.fail('Any(...) is no longer supported. Use cast(Any, ...) instead', expr)
        elif refers_to_fullname(expr.callee, 'typing._promote'):
            # Special form _promote(...).
            if not self.check_fixed_args(expr, 1, '_promote'):
                return
            # Translate first argument to an unanalyzed type.
            try:
                target = expr_to_unanalyzed_type(expr.args[0])
            except TypeTranslationError:
                self.fail('Argument 1 to _promote is not a type', expr)
                return
            expr.analyzed = PromoteExpr(target)
            expr.analyzed.line = expr.line
            expr.analyzed.accept(self)
        elif refers_to_fullname(expr.callee, 'builtins.dict'):
            expr.analyzed = self.translate_dict_call(expr)
        else:
            # Normal call expression.
            for a in expr.args:
                a.accept(self)

            if (isinstance(expr.callee, MemberExpr) and
                    isinstance(expr.callee.expr, NameExpr) and
                    expr.callee.expr.name == '__all__' and
                    expr.callee.expr.kind == GDEF and
                    expr.callee.name in ('append', 'extend')):
                if expr.callee.name == 'append' and expr.args:
                    self.add_exports(expr.args[0])
                elif (expr.callee.name == 'extend' and expr.args and
                        isinstance(expr.args[0], (ListExpr, TupleExpr))):
                    self.add_exports(*expr.args[0].items)

    def translate_dict_call(self, call: CallExpr) -> Optional[DictExpr]:
        """Translate 'dict(x=y, ...)' to {'x': y, ...}.

        For other variants of dict(...), return None.
        """
        if not call.args:
            return None
        if not all(kind == ARG_NAMED for kind in call.arg_kinds):
            # Must still accept those args.
            for a in call.args:
                a.accept(self)
            return None
        expr = DictExpr([(StrExpr(key), value)
                         for key, value in zip(call.arg_names, call.args)])
        expr.set_line(call)
        expr.accept(self)
        return expr

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
        if isinstance(base, RefExpr) and base.kind == MODULE_REF:
            # This branch handles the case foo.bar where foo is a module.
            # In this case base.node is the module's MypyFile and we look up
            # bar in its namespace.  This must be done for all types of bar.
            file = cast(Optional[MypyFile], base.node)  # can't use isinstance due to issue #2999
            n = file.names.get(expr.name, None) if file is not None else None
            if n:
                n = self.normalize_type_alias(n, expr)
                if not n:
                    return
                expr.kind = n.kind
                expr.fullname = n.fullname
                expr.node = n.node
            else:
                # We only catch some errors here; the rest will be
                # caught during type checking.
                #
                # This way we can report a larger number of errors in
                # one type checker run. If we reported errors here,
                # the build would terminate after semantic analysis
                # and we wouldn't be able to report any type errors.
                full_name = '%s.%s' % (file.fullname() if file is not None else None, expr.name)
                mod_name = " '%s'" % file.fullname() if file is not None else ''
                if full_name in obsolete_name_mapping:
                    self.fail("Module%s has no attribute %r (it's now called %r)" % (
                        mod_name, expr.name, obsolete_name_mapping[full_name]), expr)
        elif isinstance(base, RefExpr) and isinstance(base.node, TypeInfo):
            n = base.node.names.get(expr.name)
            if n is not None and (n.kind == MODULE_REF or isinstance(n.node, TypeInfo)):
                # This branch handles the case C.bar where C is a class and
                # bar is a type definition or a module resulting from
                # `import bar` inside class C. Here base.node is a TypeInfo,
                # and again we look up the name in its namespace.
                # This is done only when bar is a module or a type; other
                # things (e.g. methods) are handled by other code in checkmember.
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
        if (isinstance(expr.base, RefExpr)
                and isinstance(expr.base.node, TypeInfo)
                and not expr.base.node.is_generic()):
            expr.index.accept(self)
        elif isinstance(expr.base, RefExpr) and expr.base.kind == TYPE_ALIAS:
            # Special form -- subscripting a generic type alias.
            # Perform the type substitution and create a new alias.
            res = analyze_type_alias(expr,
                                     self.lookup_qualified,
                                     self.lookup_fully_qualified,
                                     self.fail, allow_unnormalized=self.is_stub_file)
            expr.analyzed = TypeAliasExpr(res, fallback=self.alias_fallback(res),
                                          in_runtime=True)
        elif refers_to_class_or_function(expr.base):
            # Special form -- type application.
            # Translate index to an unanalyzed type.
            types = []  # type: List[Type]
            if isinstance(expr.index, TupleExpr):
                items = expr.index.items
            else:
                items = [expr.index]
            for item in items:
                try:
                    typearg = expr_to_unanalyzed_type(item)
                except TypeTranslationError:
                    self.fail('Type expected within [...]', expr)
                    return
                typearg = self.anal_type(typearg, aliasing=True)
                types.append(typearg)
            expr.analyzed = TypeApplication(expr.base, types)
            expr.analyzed.line = expr.line
            # list, dict, set are not directly subscriptable
            n = self.lookup_type_node(expr.base)
            if n and not n.normalized and n.fullname in nongen_builtins:
                self.fail(no_subscript_builtin_alias(n.fullname, propose_alt=False), expr)
        else:
            expr.index.accept(self)

    def lookup_type_node(self, expr: Expression) -> Optional[SymbolTableNode]:
        try:
            t = expr_to_unanalyzed_type(expr)
        except TypeTranslationError:
            return None
        if isinstance(t, UnboundType):
            n = self.lookup_qualified(t.name, expr)
            return n
        return None

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

    def visit_reveal_type_expr(self, expr: RevealTypeExpr) -> None:
        expr.expr.accept(self)

    def visit_type_application(self, expr: TypeApplication) -> None:
        expr.expr.accept(self)
        for i in range(len(expr.types)):
            expr.types[i] = self.anal_type(expr.types[i])

    def visit_list_comprehension(self, expr: ListComprehension) -> None:
        expr.generator.accept(self)

    def visit_set_comprehension(self, expr: SetComprehension) -> None:
        expr.generator.accept(self)

    def visit_dictionary_comprehension(self, expr: DictionaryComprehension) -> None:
        self.enter()
        self.analyze_comp_for(expr)
        expr.key.accept(self)
        expr.value.accept(self)
        self.leave()
        self.analyze_comp_for_2(expr)

    def visit_generator_expr(self, expr: GeneratorExpr) -> None:
        self.enter()
        self.analyze_comp_for(expr)
        expr.left_expr.accept(self)
        self.leave()
        self.analyze_comp_for_2(expr)

    def analyze_comp_for(self, expr: Union[GeneratorExpr,
                                           DictionaryComprehension]) -> None:
        """Analyses the 'comp_for' part of comprehensions (part 1).

        That is the part after 'for' in (x for x in l if p). This analyzes
        variables and conditions which are analyzed in a local scope.
        """
        for i, (index, sequence, conditions) in enumerate(zip(expr.indices,
                                                              expr.sequences,
                                                              expr.condlists)):
            if i > 0:
                sequence.accept(self)
            # Bind index variables.
            self.analyze_lvalue(index)
            for cond in conditions:
                cond.accept(self)

    def analyze_comp_for_2(self, expr: Union[GeneratorExpr,
                                             DictionaryComprehension]) -> None:
        """Analyses the 'comp_for' part of comprehensions (part 2).

        That is the part after 'for' in (x for x in l if p). This analyzes
        the 'l' part which is analyzed in the surrounding scope.
        """
        expr.sequences[0].accept(self)

    def visit_lambda_expr(self, expr: LambdaExpr) -> None:
        self.analyze_function(expr)

    def visit_conditional_expr(self, expr: ConditionalExpr) -> None:
        expr.if_expr.accept(self)
        expr.cond.accept(self)
        expr.else_expr.accept(self)

    def visit_backquote_expr(self, expr: BackquoteExpr) -> None:
        expr.expr.accept(self)

    def visit__promote_expr(self, expr: PromoteExpr) -> None:
        expr.type = self.anal_type(expr.type)

    def visit_yield_expr(self, expr: YieldExpr) -> None:
        if not self.is_func_scope():
            self.fail("'yield' outside function", expr, True, blocker=True)
        else:
            if self.function_stack[-1].is_coroutine:
                if self.options.python_version < (3, 6):
                    self.fail("'yield' in async function", expr, True, blocker=True)
                else:
                    self.function_stack[-1].is_generator = True
                    self.function_stack[-1].is_async_generator = True
            else:
                self.function_stack[-1].is_generator = True
        if expr.expr:
            expr.expr.accept(self)

    def visit_await_expr(self, expr: AwaitExpr) -> None:
        if not self.is_func_scope():
            self.fail("'await' outside function", expr)
        elif not self.function_stack[-1].is_coroutine:
            self.fail("'await' outside coroutine ('async def')", expr)
        expr.expr.accept(self)

    #
    # Helpers
    #

    def lookup(self, name: str, ctx: Context) -> SymbolTableNode:
        """Look up an unqualified name in all active namespaces."""
        # 1a. Name declared using 'global x' takes precedence
        if name in self.global_decls[-1]:
            if name in self.globals:
                return self.globals[name]
            else:
                self.name_not_defined(name, ctx)
                return None
        # 1b. Name declared using 'nonlocal x' takes precedence
        if name in self.nonlocal_decls[-1]:
            for table in reversed(self.locals[:-1]):
                if table is not None and name in table:
                    return table[name]
            else:
                self.name_not_defined(name, ctx)
                return None
        # 2. Class attributes (if within class definition)
        if self.is_class_scope() and name in self.type.names:
            return self.type.names[name]
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
            assert isinstance(b.node, MypyFile)
            table = b.node.names
            if name in table:
                if name[0] == "_" and name[1] != "_":
                    self.name_not_defined(name, ctx)
                    return None
                node = table[name]
                return node
        # Give up.
        self.name_not_defined(name, ctx)
        self.check_for_obsolete_short_name(name, ctx)
        return None

    def check_for_obsolete_short_name(self, name: str, ctx: Context) -> None:
        matches = [obsolete_name
                   for obsolete_name in obsolete_name_mapping
                   if obsolete_name.rsplit('.', 1)[-1] == name]
        if len(matches) == 1:
            self.note("(Did you mean '{}'?)".format(obsolete_name_mapping[matches[0]]), ctx)

    def lookup_qualified(self, name: str, ctx: Context) -> SymbolTableNode:
        if '.' not in name:
            return self.lookup(name, ctx)
        else:
            parts = name.split('.')
            n = self.lookup(parts[0], ctx)  # type: SymbolTableNode
            if n:
                for i in range(1, len(parts)):
                    if isinstance(n.node, TypeInfo):
                        if n.node.mro is None:
                            # We haven't yet analyzed the class `n.node`.  Fall back to direct
                            # lookup in the names declared directly under it, without its base
                            # classes.  This can happen when we have a forward reference to a
                            # nested class, and the reference is bound before the outer class
                            # has been fully semantically analyzed.
                            #
                            # A better approach would be to introduce a new analysis pass or
                            # to move things around between passes, but this unblocks a common
                            # use case even though this is a little limited in case there is
                            # inheritance involved.
                            result = n.node.names.get(parts[i])
                        else:
                            result = n.node.get(parts[i])
                        n = result
                    elif isinstance(n.node, MypyFile):
                        n = n.node.names.get(parts[i], None)
                    # TODO: What if node is Var or FuncDef?
                    if not n:
                        self.name_not_defined(name, ctx)
                        break
                if n:
                    n = self.normalize_type_alias(n, ctx)
            return n

    def builtin_type(self, fully_qualified_name: str) -> Instance:
        node = self.lookup_fully_qualified(fully_qualified_name)
        assert isinstance(node.node, TypeInfo)
        return Instance(node.node, [])

    def lookup_fully_qualified(self, name: str) -> SymbolTableNode:
        """Lookup a fully qualified name.

        Assume that the name is defined. This happens in the global namespace -- the local
        module namespace is ignored.
        """
        assert '.' in name
        parts = name.split('.')
        n = self.modules[parts[0]]
        for i in range(1, len(parts) - 1):
            next_sym = n.names[parts[i]]
            assert isinstance(next_sym.node, MypyFile)
            n = next_sym.node
        return n.names.get(parts[-1])

    def lookup_fully_qualified_or_none(self, name: str) -> Optional[SymbolTableNode]:
        """Lookup a fully qualified name.

        Assume that the name is defined. This happens in the global namespace -- the local
        module namespace is ignored.
        """
        assert '.' in name
        parts = name.split('.')
        n = self.modules[parts[0]]
        for i in range(1, len(parts) - 1):
            next_sym = n.names.get(parts[i])
            if not next_sym:
                return None
            assert isinstance(next_sym.node, MypyFile)
            n = next_sym.node
        return n.names.get(parts[-1])

    def qualified_name(self, n: str) -> str:
        if self.type is not None:
            base = self.type._fullname
        else:
            base = self.cur_mod_id
        return base + '.' + n

    def enter(self) -> None:
        self.locals.append(SymbolTable())
        self.global_decls.append(set())
        self.nonlocal_decls.append(set())
        # -1 since entering block will increment this to 0.
        self.block_depth.append(-1)

    def leave(self) -> None:
        self.locals.pop()
        self.global_decls.pop()
        self.nonlocal_decls.pop()
        self.block_depth.pop()

    def is_func_scope(self) -> bool:
        return self.locals[-1] is not None

    def is_class_scope(self) -> bool:
        return self.type is not None and not self.is_func_scope()

    def is_module_scope(self) -> bool:
        return not (self.is_class_scope() or self.is_func_scope())

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
            existing = self.globals.get(name)
            if existing and (not isinstance(node.node, MypyFile) or
                             existing.node != node.node) and existing.kind != UNBOUND_IMPORTED:
                # Modules can be imported multiple times to support import
                # of multiple submodules of a package (e.g. a.x and a.y).
                ok = False
                # Only report an error if the symbol collision provides a different type.
                if existing.type and node.type and is_same_type(existing.type, node.type):
                    ok = True
                if not ok:
                    self.name_already_defined(name, context)
            self.globals[name] = node

    def add_local(self, node: Union[Var, FuncDef, OverloadedFuncDef], ctx: Context) -> None:
        name = node.name()
        if name in self.locals[-1]:
            self.name_already_defined(name, ctx)
        node._fullname = name
        self.locals[-1][name] = SymbolTableNode(LDEF, node)

    def add_exports(self, *exps: Expression) -> None:
        for exp in exps:
            if isinstance(exp, StrExpr):
                self.all_exports.add(exp.value)

    def check_no_global(self, n: str, ctx: Context,
                        is_overloaded_func: bool = False) -> None:
        if n in self.globals:
            prev_is_overloaded = isinstance(self.globals[n], OverloadedFuncDef)
            if is_overloaded_func and prev_is_overloaded:
                self.fail("Nonconsecutive overload {} found".format(n), ctx)
            elif prev_is_overloaded:
                self.fail("Definition of '{}' missing 'overload'".format(n), ctx)
            else:
                self.name_already_defined(n, ctx)

    def name_not_defined(self, name: str, ctx: Context) -> None:
        message = "Name '{}' is not defined".format(name)
        extra = self.undefined_name_extra_info(name)
        if extra:
            message += ' {}'.format(extra)
        self.fail(message, ctx)

    def name_already_defined(self, name: str, ctx: Context) -> None:
        self.fail("Name '{}' already defined".format(name), ctx)

    def fail(self, msg: str, ctx: Context, serious: bool = False, *,
             blocker: bool = False) -> None:
        if (not serious and
                not self.options.check_untyped_defs and
                self.function_stack and
                self.function_stack[-1].is_dynamic()):
            return
        # In case it's a bug and we don't really have context
        assert ctx is not None, msg
        self.errors.report(ctx.get_line(), ctx.get_column(), msg, blocker=blocker)

    def fail_blocker(self, msg: str, ctx: Context) -> None:
        self.fail(msg, ctx, blocker=True)

    def note(self, msg: str, ctx: Context) -> None:
        if (not self.options.check_untyped_defs and
                self.function_stack and
                self.function_stack[-1].is_dynamic()):
            return
        self.errors.report(ctx.get_line(), ctx.get_column(), msg, severity='note')

    def undefined_name_extra_info(self, fullname: str) -> Optional[str]:
        if fullname in obsolete_name_mapping:
            return "(it's now called '{}')".format(obsolete_name_mapping[fullname])
        else:
            return None

    def accept(self, node: Node) -> None:
        try:
            node.accept(self)
        except Exception as err:
            report_internal_error(err, self.errors.file, node.line, self.errors, self.options)


class FirstPass(NodeVisitor):
    """First phase of semantic analysis.

    See docstring of 'analyze()' below for a description of what this does.
    """

    def __init__(self, sem: SemanticAnalyzer) -> None:
        self.sem = sem

    def visit_file(self, file: MypyFile, fnam: str, mod_id: str, options: Options) -> None:
        """Perform the first analysis pass.

        Populate module global table.  Resolve the full names of
        definitions not nested within functions and construct type
        info structures, but do not resolve inter-definition
        references such as base classes.

        Also add implicit definitions such as __name__.

        In this phase we don't resolve imports. For 'from ... import',
        we generate dummy symbol table nodes for the imported names,
        and these will get resolved in later phases of semantic
        analysis.
        """
        sem = self.sem
        self.sem.options = options  # Needed because we sometimes call into it
        self.pyversion = options.python_version
        self.platform = options.platform
        sem.cur_mod_id = mod_id
        sem.errors.set_file(fnam)
        sem.globals = SymbolTable()
        sem.global_decls = [set()]
        sem.nonlocal_decls = [set()]
        sem.block_depth = [0]

        defs = file.defs

        # Add implicit definitions of module '__name__' etc.
        for name, t in implicit_module_attrs.items():
            # unicode docstrings should be accepted in Python 2
            if name == '__doc__':
                if self.pyversion >= (3, 0):
                    typ = UnboundType('__builtins__.str')  # type: Type
                else:
                    typ = UnionType([UnboundType('__builtins__.str'),
                                     UnboundType('__builtins__.unicode')])
            else:
                assert t is not None, 'type should be specified for {}'.format(name)
                typ = UnboundType(t)
            v = Var(name, typ)
            v._fullname = self.sem.qualified_name(name)
            self.sem.globals[name] = SymbolTableNode(GDEF, v, self.sem.cur_mod_id)

        for d in defs:
            d.accept(self)

        # Add implicit definition of literals/keywords to builtins, as we
        # cannot define a variable with them explicitly.
        if mod_id == 'builtins':
            literal_types = [
                ('None', NoneTyp()),
                # reveal_type is a mypy-only function that gives an error with the type of its arg
                ('reveal_type', AnyType()),
            ]  # type: List[Tuple[str, Type]]

            # TODO(ddfisher): This guard is only needed because mypy defines
            # fake builtins for its tests which often don't define bool.  If
            # mypy is fast enough that we no longer need those, this
            # conditional check should be removed.
            if 'bool' in self.sem.globals:
                bool_type = self.sem.named_type('bool')
                literal_types.extend([
                    ('True', bool_type),
                    ('False', bool_type),
                    ('__debug__', bool_type),
                ])

            for name, typ in literal_types:
                v = Var(name, typ)
                v._fullname = self.sem.qualified_name(name)
                self.sem.globals[name] = SymbolTableNode(GDEF, v, self.sem.cur_mod_id)

        del self.sem.options

    def visit_block(self, b: Block) -> None:
        if b.is_unreachable:
            return
        self.sem.block_depth[-1] += 1
        for node in b.body:
            node.accept(self)
        self.sem.block_depth[-1] -= 1

    def visit_assignment_stmt(self, s: AssignmentStmt) -> None:
        if self.sem.is_module_scope():
            for lval in s.lvalues:
                self.analyze_lvalue(lval, explicit_type=s.type is not None)

    def visit_func_def(self, func: FuncDef) -> None:
        sem = self.sem
        func.is_conditional = sem.block_depth[-1] > 0
        func._fullname = sem.qualified_name(func.name())
        at_module = sem.is_module_scope()
        if at_module and func.name() in sem.globals:
            # Already defined in this module.
            original_sym = sem.globals[func.name()]
            if original_sym.kind == UNBOUND_IMPORTED:
                # Ah this is an imported name. We can't resolve them now, so we'll postpone
                # this until the main phase of semantic analysis.
                return
            if not sem.set_original_def(original_sym.node, func):
                # Report error.
                sem.check_no_global(func.name(), func)
        else:
            if at_module:
                sem.globals[func.name()] = SymbolTableNode(GDEF, func, sem.cur_mod_id)
            # Also analyze the function body (in case there are conditional imports).
            sem.function_stack.append(func)
            sem.errors.push_function(func.name())
            sem.enter()
            func.body.accept(self)
            sem.leave()
            sem.errors.pop_function()
            sem.function_stack.pop()

    def visit_overloaded_func_def(self, func: OverloadedFuncDef) -> None:
        kind = self.kind_by_scope()
        if kind == GDEF:
            self.sem.check_no_global(func.name(), func, True)
        func._fullname = self.sem.qualified_name(func.name())
        if kind == GDEF:
            self.sem.globals[func.name()] = SymbolTableNode(kind, func, self.sem.cur_mod_id)
        if func.impl:
            impl = func.impl
            # Also analyze the function body (in case there are conditional imports).
            sem = self.sem

            if isinstance(impl, FuncDef):
                sem.function_stack.append(impl)
                sem.errors.push_function(func.name())
                sem.enter()
                impl.body.accept(self)
            elif isinstance(impl, Decorator):
                sem.function_stack.append(impl.func)
                sem.errors.push_function(func.name())
                sem.enter()
                impl.func.body.accept(self)
            else:
                assert False, "Implementation of an overload needs to be FuncDef or Decorator"
            sem.leave()
            sem.errors.pop_function()
            sem.function_stack.pop()

    def visit_class_def(self, cdef: ClassDef) -> None:
        kind = self.kind_by_scope()
        if kind == LDEF:
            return
        elif kind == GDEF:
            self.sem.check_no_global(cdef.name, cdef)
        cdef.fullname = self.sem.qualified_name(cdef.name)
        info = TypeInfo(SymbolTable(), cdef, self.sem.cur_mod_id)
        info.set_line(cdef.line, cdef.column)
        cdef.info = info
        if kind == GDEF:
            self.sem.globals[cdef.name] = SymbolTableNode(kind, info, self.sem.cur_mod_id)
        self.process_nested_classes(cdef)

    def process_nested_classes(self, outer_def: ClassDef) -> None:
        self.sem.enter_class(outer_def)
        for node in outer_def.defs.body:
            if isinstance(node, ClassDef):
                node.info = TypeInfo(SymbolTable(), node, self.sem.cur_mod_id)
                if outer_def.fullname:
                    node.info._fullname = outer_def.fullname + '.' + node.info.name()
                else:
                    node.info._fullname = node.info.name()
                node.fullname = node.info._fullname
                symbol = SymbolTableNode(MDEF, node.info)
                outer_def.info.names[node.name] = symbol
                self.process_nested_classes(node)
            elif isinstance(node, (ImportFrom, Import, ImportAll, IfStmt)):
                node.accept(self)
        self.sem.leave_class()

    def visit_import_from(self, node: ImportFrom) -> None:
        # We can't bind module names during the first pass, as the target module might be
        # unprocessed. However, we add dummy unbound imported names to the symbol table so
        # that we at least know that the name refers to a module.
        at_module = self.sem.is_module_scope()
        node.is_top_level = at_module
        if not at_module:
            return
        for name, as_name in node.names:
            imported_name = as_name or name
            if imported_name not in self.sem.globals:
                self.sem.add_symbol(imported_name, SymbolTableNode(UNBOUND_IMPORTED, None), node)

    def visit_import(self, node: Import) -> None:
        node.is_top_level = self.sem.is_module_scope()
        # This is similar to visit_import_from -- see the comment there.
        if not self.sem.is_module_scope():
            return
        for id, as_id in node.ids:
            imported_id = as_id or id
            if imported_id not in self.sem.globals:
                self.sem.add_symbol(imported_id, SymbolTableNode(UNBOUND_IMPORTED, None), node)
            else:
                # If the previous symbol is a variable, this should take precedence.
                self.sem.globals[imported_id] = SymbolTableNode(UNBOUND_IMPORTED, None)

    def visit_import_all(self, node: ImportAll) -> None:
        node.is_top_level = self.sem.is_module_scope()

    def visit_while_stmt(self, s: WhileStmt) -> None:
        if self.sem.is_module_scope():
            s.body.accept(self)
            if s.else_body:
                s.else_body.accept(self)

    def visit_for_stmt(self, s: ForStmt) -> None:
        if self.sem.is_module_scope():
            self.analyze_lvalue(s.index, explicit_type=s.index_type is not None)
            s.body.accept(self)
            if s.else_body:
                s.else_body.accept(self)

    def visit_with_stmt(self, s: WithStmt) -> None:
        if self.sem.is_module_scope():
            for n in s.target:
                if n:
                    self.analyze_lvalue(n, explicit_type=s.target_type is not None)
            s.body.accept(self)

    def visit_decorator(self, d: Decorator) -> None:
        d.var._fullname = self.sem.qualified_name(d.var.name())
        self.sem.add_symbol(d.var.name(), SymbolTableNode(self.kind_by_scope(), d.var), d)

    def visit_if_stmt(self, s: IfStmt) -> None:
        infer_reachability_of_if_statement(s, pyversion=self.pyversion, platform=self.platform)
        for node in s.body:
            node.accept(self)
        if s.else_body:
            s.else_body.accept(self)

    def visit_try_stmt(self, s: TryStmt) -> None:
        if self.sem.is_module_scope():
            self.sem.analyze_try_stmt(s, self, add_global=self.sem.is_module_scope())

    def analyze_lvalue(self, lvalue: Lvalue, explicit_type: bool = False) -> None:
        self.sem.analyze_lvalue(lvalue, add_global=self.sem.is_module_scope(),
                                explicit_type=explicit_type)

    def kind_by_scope(self) -> int:
        if self.sem.is_module_scope():
            return GDEF
        elif self.sem.is_class_scope():
            return MDEF
        elif self.sem.is_func_scope():
            return LDEF
        else:
            assert False, "Couldn't determine scope"


class ThirdPass(TraverserVisitor):
    """The third and final pass of semantic analysis.

    Check type argument counts and values of generic types, and perform some
    straightforward type inference.
    """

    def __init__(self, modules: Dict[str, MypyFile], errors: Errors) -> None:
        self.modules = modules
        self.errors = errors

    def visit_file(self, file_node: MypyFile, fnam: str, options: Options) -> None:
        self.errors.set_file(fnam)
        self.options = options
        self.accept(file_node)

    def accept(self, node: Node) -> None:
        try:
            node.accept(self)
        except Exception as err:
            report_internal_error(err, self.errors.file, node.line, self.errors, self.options)

    def visit_block(self, b: Block) -> None:
        if b.is_unreachable:
            return
        super().visit_block(b)

    def visit_func_def(self, fdef: FuncDef) -> None:
        self.errors.push_function(fdef.name())
        self.analyze(fdef.type)
        super().visit_func_def(fdef)
        self.errors.pop_function()

    def visit_class_def(self, tdef: ClassDef) -> None:
        for type in tdef.info.bases:
            self.analyze(type)
        # Recompute MRO now that we have analyzed all modules, to pick
        # up superclasses of bases imported from other modules in an
        # import loop. (Only do so if we succeeded the first time.)
        if tdef.info.mro:
            tdef.info.mro = []  # Force recomputation
            calculate_class_mro(tdef, self.fail_blocker)
        super().visit_class_def(tdef)

    def visit_decorator(self, dec: Decorator) -> None:
        """Try to infer the type of the decorated function.

        This lets us resolve references to decorated functions during
        type checking when there are cyclic imports, as otherwise the
        type might not be available when we need it.

        This basically uses a simple special-purpose type inference
        engine just for decorators.
        """
        super().visit_decorator(dec)
        if dec.var.is_property:
            # Decorators are expected to have a callable type (it's a little odd).
            if dec.func.type is None:
                dec.var.type = CallableType(
                    [AnyType()],
                    [ARG_POS],
                    [None],
                    AnyType(),
                    self.builtin_type('function'),
                    name=dec.var.name())
            elif isinstance(dec.func.type, CallableType):
                dec.var.type = dec.func.type
            return
        decorator_preserves_type = True
        for expr in dec.decorators:
            preserve_type = False
            if isinstance(expr, RefExpr) and isinstance(expr.node, FuncDef):
                if is_identity_signature(expr.node.type):
                    preserve_type = True
            if not preserve_type:
                decorator_preserves_type = False
                break
        if decorator_preserves_type:
            # No non-identity decorators left. We can trivially infer the type
            # of the function here.
            dec.var.type = function_type(dec.func, self.builtin_type('function'))
        if dec.decorators:
            if returns_any_if_called(dec.decorators[0]):
                # The outermost decorator will return Any so we know the type of the
                # decorated function.
                dec.var.type = AnyType()
            sig = find_fixed_callable_return(dec.decorators[0])
            if sig:
                # The outermost decorator always returns the same kind of function,
                # so we know that this is the type of the decoratored function.
                orig_sig = function_type(dec.func, self.builtin_type('function'))
                sig.name = orig_sig.items()[0].name
                dec.var.type = sig

    def visit_assignment_stmt(self, s: AssignmentStmt) -> None:
        self.analyze(s.type)
        if isinstance(s.rvalue, IndexExpr) and isinstance(s.rvalue.analyzed, TypeAliasExpr):
            self.analyze(s.rvalue.analyzed.type)
        super().visit_assignment_stmt(s)

    def visit_cast_expr(self, e: CastExpr) -> None:
        self.analyze(e.type)
        super().visit_cast_expr(e)

    def visit_reveal_type_expr(self, e: RevealTypeExpr) -> None:
        super().visit_reveal_type_expr(e)

    def visit_type_application(self, e: TypeApplication) -> None:
        for type in e.types:
            self.analyze(type)
        super().visit_type_application(e)

    # Helpers

    def analyze(self, type: Type) -> None:
        if type:
            analyzer = TypeAnalyserPass3(self.fail)
            type.accept(analyzer)

    def fail(self, msg: str, ctx: Context, *, blocker: bool = False) -> None:
        self.errors.report(ctx.get_line(), ctx.get_column(), msg)

    def fail_blocker(self, msg: str, ctx: Context) -> None:
        self.fail(msg, ctx, blocker=True)

    def builtin_type(self, name: str, args: List[Type] = None) -> Instance:
        names = self.modules['builtins']
        sym = names.names[name]
        assert isinstance(sym.node, TypeInfo)
        return Instance(sym.node, args or [])


def replace_implicit_first_type(sig: FunctionLike, new: Type) -> FunctionLike:
    if isinstance(sig, CallableType):
        return sig.copy_modified(arg_types=[new] + sig.arg_types[1:])
    elif isinstance(sig, Overloaded):
        return Overloaded([cast(CallableType, replace_implicit_first_type(i, new))
                           for i in sig.items()])
    else:
        assert False


def set_callable_name(sig: Type, fdef: FuncDef) -> Type:
    if isinstance(sig, FunctionLike):
        if fdef.info:
            return sig.with_name(
                '"{}" of "{}"'.format(fdef.name(), fdef.info.name()))
        else:
            return sig.with_name('"{}"'.format(fdef.name()))
    else:
        return sig


def refers_to_fullname(node: Expression, fullname: str) -> bool:
    """Is node a name or member expression with the given full name?"""
    return isinstance(node, RefExpr) and node.fullname == fullname


def refers_to_class_or_function(node: Expression) -> bool:
    """Does semantically analyzed node refer to a class?"""
    return (isinstance(node, RefExpr) and
            isinstance(node.node, (TypeInfo, FuncDef, OverloadedFuncDef)))


def calculate_class_mro(defn: ClassDef, fail: Callable[[str, Context], None]) -> None:
    try:
        defn.info.calculate_mro()
    except MroError:
        fail("Cannot determine consistent method resolution order "
             '(MRO) for "%s"' % defn.name, defn)
        defn.info.mro = []
    # The property of falling back to Any is inherited.
    defn.info.fallback_to_any = any(baseinfo.fallback_to_any for baseinfo in defn.info.mro)


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
        assert node.kind in (BOUND_TVAR, UNBOUND_TVAR)
        node.kind = UNBOUND_TVAR


def enable_typevars(nodes: List[SymbolTableNode]) -> None:
    for node in nodes:
        assert node.kind in (BOUND_TVAR, UNBOUND_TVAR)
        node.kind = BOUND_TVAR


def remove_imported_names_from_symtable(names: SymbolTable,
                                        module: str) -> None:
    """Remove all imported names from the symbol table of a module."""
    removed = []  # type: List[str]
    for name, node in names.items():
        if node.node is None:
            continue
        fullname = node.node.fullname()
        prefix = fullname[:fullname.rfind('.')]
        if prefix != module:
            removed.append(name)
    for name in removed:
        del names[name]


def infer_reachability_of_if_statement(s: IfStmt,
                                       pyversion: Tuple[int, int],
                                       platform: str) -> None:
    for i in range(len(s.expr)):
        result = infer_if_condition_value(s.expr[i], pyversion, platform)
        if result in (ALWAYS_FALSE, MYPY_FALSE):
            # The condition is considered always false, so we skip the if/elif body.
            mark_block_unreachable(s.body[i])
        elif result in (ALWAYS_TRUE, MYPY_TRUE):
            # This condition is considered always true, so all of the remaining
            # elif/else bodies should not be checked.
            if result == MYPY_TRUE:
                # This condition is false at runtime; this will affect
                # import priorities.
                mark_block_mypy_only(s.body[i])
            for body in s.body[i + 1:]:
                mark_block_unreachable(body)
            if s.else_body:
                mark_block_unreachable(s.else_body)
            break


def infer_if_condition_value(expr: Expression, pyversion: Tuple[int, int], platform: str) -> int:
    """Infer whether if condition is always true/false.

    Return ALWAYS_TRUE if always true, ALWAYS_FALSE if always false,
    MYPY_TRUE if true under mypy and false at runtime, MYPY_FALSE if
    false under mypy and true at runtime, else TRUTH_VALUE_UNKNOWN.
    """
    name = ''
    negated = False
    alias = expr
    if isinstance(alias, UnaryExpr):
        if alias.op == 'not':
            expr = alias.expr
            negated = True
    result = TRUTH_VALUE_UNKNOWN
    if isinstance(expr, NameExpr):
        name = expr.name
    elif isinstance(expr, MemberExpr):
        name = expr.name
    else:
        result = consider_sys_version_info(expr, pyversion)
        if result == TRUTH_VALUE_UNKNOWN:
            result = consider_sys_platform(expr, platform)
    if result == TRUTH_VALUE_UNKNOWN:
        if name == 'PY2':
            result = ALWAYS_TRUE if pyversion[0] == 2 else ALWAYS_FALSE
        elif name == 'PY3':
            result = ALWAYS_TRUE if pyversion[0] == 3 else ALWAYS_FALSE
        elif name == 'MYPY' or name == 'TYPE_CHECKING':
            result = MYPY_TRUE
    if negated:
        result = inverted_truth_mapping[result]
    return result


def consider_sys_version_info(expr: Expression, pyversion: Tuple[int, ...]) -> int:
    """Consider whether expr is a comparison involving sys.version_info.

    Return ALWAYS_TRUE, ALWAYS_FALSE, or TRUTH_VALUE_UNKNOWN.
    """
    # Cases supported:
    # - sys.version_info[<int>] <compare_op> <int>
    # - sys.version_info[:<int>] <compare_op> <tuple_of_n_ints>
    # - sys.version_info <compare_op> <tuple_of_1_or_2_ints>
    #   (in this case <compare_op> must be >, >=, <, <=, but cannot be ==, !=)
    if not isinstance(expr, ComparisonExpr):
        return TRUTH_VALUE_UNKNOWN
    # Let's not yet support chained comparisons.
    if len(expr.operators) > 1:
        return TRUTH_VALUE_UNKNOWN
    op = expr.operators[0]
    if op not in ('==', '!=', '<=', '>=', '<', '>'):
        return TRUTH_VALUE_UNKNOWN
    thing = contains_int_or_tuple_of_ints(expr.operands[1])
    if thing is None:
        return TRUTH_VALUE_UNKNOWN
    index = contains_sys_version_info(expr.operands[0])
    if isinstance(index, int) and isinstance(thing, int):
        # sys.version_info[i] <compare_op> k
        if 0 <= index <= 1:
            return fixed_comparison(pyversion[index], op, thing)
        else:
            return TRUTH_VALUE_UNKNOWN
    elif isinstance(index, tuple) and isinstance(thing, tuple):
        # Why doesn't mypy see that index can't be None here?
        lo, hi = cast(tuple, index)
        if lo is None:
            lo = 0
        if hi is None:
            hi = 2
        if 0 <= lo < hi <= 2:
            val = pyversion[lo:hi]
            if len(val) == len(thing) or len(val) > len(thing) and op not in ('==', '!='):
                return fixed_comparison(val, op, thing)
    return TRUTH_VALUE_UNKNOWN


def consider_sys_platform(expr: Expression, platform: str) -> int:
    """Consider whether expr is a comparison involving sys.platform.

    Return ALWAYS_TRUE, ALWAYS_FALSE, or TRUTH_VALUE_UNKNOWN.
    """
    # Cases supported:
    # - sys.platform == 'posix'
    # - sys.platform != 'win32'
    # - sys.platform.startswith('win')
    if isinstance(expr, ComparisonExpr):
        # Let's not yet support chained comparisons.
        if len(expr.operators) > 1:
            return TRUTH_VALUE_UNKNOWN
        op = expr.operators[0]
        if op not in ('==', '!='):
            return TRUTH_VALUE_UNKNOWN
        if not is_sys_attr(expr.operands[0], 'platform'):
            return TRUTH_VALUE_UNKNOWN
        right = expr.operands[1]
        if not isinstance(right, (StrExpr, UnicodeExpr)):
            return TRUTH_VALUE_UNKNOWN
        return fixed_comparison(platform, op, right.value)
    elif isinstance(expr, CallExpr):
        if not isinstance(expr.callee, MemberExpr):
            return TRUTH_VALUE_UNKNOWN
        if len(expr.args) != 1 or not isinstance(expr.args[0], (StrExpr, UnicodeExpr)):
            return TRUTH_VALUE_UNKNOWN
        if not is_sys_attr(expr.callee.expr, 'platform'):
            return TRUTH_VALUE_UNKNOWN
        if expr.callee.name != 'startswith':
            return TRUTH_VALUE_UNKNOWN
        if platform.startswith(expr.args[0].value):
            return ALWAYS_TRUE
        else:
            return ALWAYS_FALSE
    else:
        return TRUTH_VALUE_UNKNOWN


Targ = TypeVar('Targ', int, str, Tuple[int, ...])


def fixed_comparison(left: Targ, op: str, right: Targ) -> int:
    rmap = {False: ALWAYS_FALSE, True: ALWAYS_TRUE}
    if op == '==':
        return rmap[left == right]
    if op == '!=':
        return rmap[left != right]
    if op == '<=':
        return rmap[left <= right]
    if op == '>=':
        return rmap[left >= right]
    if op == '<':
        return rmap[left < right]
    if op == '>':
        return rmap[left > right]
    return TRUTH_VALUE_UNKNOWN


def contains_int_or_tuple_of_ints(expr: Expression
                                  ) -> Union[None, int, Tuple[int], Tuple[int, ...]]:
    if isinstance(expr, IntExpr):
        return expr.value
    if isinstance(expr, TupleExpr):
        if expr.literal == LITERAL_YES:
            thing = []
            for x in expr.items:
                if not isinstance(x, IntExpr):
                    return None
                thing.append(x.value)
            return tuple(thing)
    return None


def contains_sys_version_info(expr: Expression
                              ) -> Union[None, int, Tuple[Optional[int], Optional[int]]]:
    if is_sys_attr(expr, 'version_info'):
        return (None, None)  # Same as sys.version_info[:]
    if isinstance(expr, IndexExpr) and is_sys_attr(expr.base, 'version_info'):
        index = expr.index
        if isinstance(index, IntExpr):
            return index.value
        if isinstance(index, SliceExpr):
            if index.stride is not None:
                if not isinstance(index.stride, IntExpr) or index.stride.value != 1:
                    return None
            begin = end = None
            if index.begin_index is not None:
                if not isinstance(index.begin_index, IntExpr):
                    return None
                begin = index.begin_index.value
            if index.end_index is not None:
                if not isinstance(index.end_index, IntExpr):
                    return None
                end = index.end_index.value
            return (begin, end)
    return None


def is_sys_attr(expr: Expression, name: str) -> bool:
    # TODO: This currently doesn't work with code like this:
    # - import sys as _sys
    # - from sys import version_info
    if isinstance(expr, MemberExpr) and expr.name == name:
        if isinstance(expr.expr, NameExpr) and expr.expr.name == 'sys':
            # TODO: Guard against a local named sys, etc.
            # (Though later passes will still do most checking.)
            return True
    return False


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


def mark_block_mypy_only(block: Block) -> None:
    block.accept(MarkImportsMypyOnlyVisitor())


class MarkImportsMypyOnlyVisitor(TraverserVisitor):
    """Visitor that sets is_mypy_only (which affects priority)."""

    def visit_import(self, node: Import) -> None:
        node.is_mypy_only = True

    def visit_import_from(self, node: ImportFrom) -> None:
        node.is_mypy_only = True

    def visit_import_all(self, node: ImportAll) -> None:
        node.is_mypy_only = True


def is_identity_signature(sig: Type) -> bool:
    """Is type a callable of form T -> T (where T is a type variable)?"""
    if isinstance(sig, CallableType) and sig.arg_kinds == [ARG_POS]:
        if isinstance(sig.arg_types[0], TypeVarType) and isinstance(sig.ret_type, TypeVarType):
            return sig.arg_types[0].id == sig.ret_type.id
    return False


def returns_any_if_called(expr: Expression) -> bool:
    """Return True if we can predict that expr will return Any if called.

    This only uses information available during semantic analysis so this
    will sometimes return False because of insufficient information (as
    type inference hasn't run yet).
    """
    if isinstance(expr, RefExpr):
        if isinstance(expr.node, FuncDef):
            typ = expr.node.type
            if typ is None:
                # No signature -> default to Any.
                return True
            # Explicit Any return?
            return isinstance(typ, CallableType) and isinstance(typ.ret_type, AnyType)
        elif isinstance(expr.node, Var):
            typ = expr.node.type
            return typ is None or isinstance(typ, AnyType)
    elif isinstance(expr, CallExpr):
        return returns_any_if_called(expr.callee)
    return False


def find_fixed_callable_return(expr: Expression) -> Optional[CallableType]:
    if isinstance(expr, RefExpr):
        if isinstance(expr.node, FuncDef):
            typ = expr.node.type
            if typ:
                if isinstance(typ, CallableType) and has_no_typevars(typ.ret_type):
                    if isinstance(typ.ret_type, CallableType):
                        return typ.ret_type
    elif isinstance(expr, CallExpr):
        t = find_fixed_callable_return(expr.callee)
        if t:
            if isinstance(t.ret_type, CallableType):
                return t.ret_type
    return None
