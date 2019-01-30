"""The semantic analyzer passes 1 and 2.

Bind names to definitions and do various other simple consistency
checks. For example, consider this program:

  x = 1
  y = x

Here semantic analysis would detect that the assignment 'x = 1'
defines a new variable, the type of which is to be inferred (in a
later pass; type inference or type checking is not part of semantic
analysis).  Also, it would bind both references to 'x' to the same
module-level variable (Var) node.  The second assignment would also
be analyzed, and the type of 'y' marked as being inferred.

Semantic analysis is the first analysis pass after parsing, and it is
subdivided into three passes:

 * SemanticAnalyzerPass1 is defined in mypy.semanal_pass1.

 * SemanticAnalyzerPass2 is the second pass.  It does the bulk of the work.
   It assumes that dependent modules have been semantically analyzed,
   up to the second pass, unless there is a import cycle.

 * SemanticAnalyzerPass3 is the third pass. It's in mypy.semanal_pass3.

Semantic analysis of types is implemented in module mypy.typeanal.

TODO: Check if the third pass slows down type checking significantly.
  We could probably get rid of it -- for example, we could collect all
  analyzed types in a collection and check them without having to
  traverse the entire AST.
"""

from contextlib import contextmanager

from typing import (
    List, Dict, Set, Tuple, cast, TypeVar, Union, Optional, Callable, Iterator, Iterable,
)

from mypy.nodes import (
    MypyFile, TypeInfo, Node, AssignmentStmt, FuncDef, OverloadedFuncDef,
    ClassDef, Var, GDEF, FuncItem, Import, Expression, Lvalue,
    ImportFrom, ImportAll, Block, LDEF, NameExpr, MemberExpr,
    IndexExpr, TupleExpr, ListExpr, ExpressionStmt, ReturnStmt,
    RaiseStmt, AssertStmt, OperatorAssignmentStmt, WhileStmt,
    ForStmt, BreakStmt, ContinueStmt, IfStmt, TryStmt, WithStmt, DelStmt,
    GlobalDecl, SuperExpr, DictExpr, CallExpr, RefExpr, OpExpr, UnaryExpr,
    SliceExpr, CastExpr, RevealExpr, TypeApplication, Context, SymbolTable,
    SymbolTableNode, ListComprehension, GeneratorExpr,
    LambdaExpr, MDEF, Decorator, SetExpr, TypeVarExpr,
    StrExpr, BytesExpr, PrintStmt, ConditionalExpr, PromoteExpr,
    ComparisonExpr, StarExpr, ARG_POS, ARG_NAMED, type_aliases,
    YieldFromExpr, NamedTupleExpr, NonlocalDecl, SymbolNode,
    SetComprehension, DictionaryComprehension, TypeAlias, TypeAliasExpr,
    YieldExpr, ExecStmt, BackquoteExpr, ImportBase, AwaitExpr,
    IntExpr, FloatExpr, UnicodeExpr, TempNode, ImportedName, OverloadPart,
    COVARIANT, CONTRAVARIANT, INVARIANT, UNBOUND_IMPORTED, LITERAL_YES, nongen_builtins,
    get_member_expr_fullname, REVEAL_TYPE, REVEAL_LOCALS, is_final_node
)
from mypy.tvar_scope import TypeVarScope
from mypy.typevars import fill_typevars
from mypy.visitor import NodeVisitor
from mypy.errors import Errors, report_internal_error
from mypy.messages import MessageBuilder
from mypy import message_registry
from mypy.types import (
    FunctionLike, UnboundType, TypeVarDef, TupleType, UnionType, StarType, function_type,
    CallableType, Overloaded, Instance, Type, AnyType, LiteralType, LiteralValue,
    TypeTranslator, TypeOfAny, TypeType, NoneTyp,
)
from mypy.nodes import implicit_module_attrs
from mypy.typeanal import (
    TypeAnalyser, analyze_type_alias, no_subscript_builtin_alias,
    TypeVariableQuery, TypeVarList, remove_dups, has_any_from_unimported_type,
    check_for_explicit_any
)
from mypy.exprtotype import expr_to_unanalyzed_type, TypeTranslationError
from mypy.sametypes import is_same_type
from mypy.options import Options
from mypy import state
from mypy.plugin import (
    Plugin, ClassDefContext, SemanticAnalyzerPluginInterface,
    DynamicClassDefContext
)
from mypy.util import get_prefix, correct_relative_import, unmangle
from mypy.semanal_shared import SemanticAnalyzerInterface, set_callable_name
from mypy.scope import Scope
from mypy.semanal_namedtuple import NamedTupleAnalyzer, NAMEDTUPLE_PROHIBITED_NAMES
from mypy.semanal_typeddict import TypedDictAnalyzer
from mypy.semanal_enum import EnumCallAnalyzer
from mypy.semanal_newtype import NewTypeAnalyzer
from mypy.reachability import (
    infer_reachability_of_if_statement, infer_condition_value, ALWAYS_FALSE, ALWAYS_TRUE,
    MYPY_TRUE, MYPY_FALSE
)
from mypy.mro import calculate_mro, MroError

MYPY = False
if MYPY:
    from typing_extensions import Final

T = TypeVar('T')


# Map from obsolete name to the current spelling.
obsolete_name_mapping = {
    'typing.Function': 'typing.Callable',
    'typing.typevar': 'typing.TypeVar',
}  # type: Final

# Hard coded type promotions (shared between all Python versions).
# These add extra ad-hoc edges to the subtyping relation. For example,
# int is considered a subtype of float, even though there is no
# subclass relationship.
TYPE_PROMOTIONS = {
    'builtins.int': 'builtins.float',
    'builtins.float': 'builtins.complex',
}  # type: Final

# Hard coded type promotions for Python 3.
#
# Note that the bytearray -> bytes promotion is a little unsafe
# as some functions only accept bytes objects. Here convenience
# trumps safety.
TYPE_PROMOTIONS_PYTHON3 = TYPE_PROMOTIONS.copy()  # type: Final
TYPE_PROMOTIONS_PYTHON3.update({
    'builtins.bytearray': 'builtins.bytes',
})

# Hard coded type promotions for Python 2.
#
# These promotions are unsafe, but we are doing them anyway
# for convenience and also for Python 3 compatibility
# (bytearray -> str).
TYPE_PROMOTIONS_PYTHON2 = TYPE_PROMOTIONS.copy()  # type: Final
TYPE_PROMOTIONS_PYTHON2.update({
    'builtins.str': 'builtins.unicode',
    'builtins.bytearray': 'builtins.str',
})

# When analyzing a function, should we analyze the whole function in one go, or
# should we only perform one phase of the analysis? The latter is used for
# nested functions. In the first phase we add the function to the symbol table
# but don't process body. In the second phase we process function body. This
# way we can have mutually recursive nested functions.
FUNCTION_BOTH_PHASES = 0  # type: Final  # Everything in one go
FUNCTION_FIRST_PHASE_POSTPONE_SECOND = 1  # type: Final  # Add to symbol table but postpone body
FUNCTION_SECOND_PHASE = 2  # type: Final  # Only analyze body

# Map from the full name of a missing definition to the test fixture (under
# test-data/unit/fixtures/) that provides the definition. This is used for
# generating better error messages when running mypy tests only.
SUGGESTED_TEST_FIXTURES = {
    'builtins.list': 'list.pyi',
    'builtins.dict': 'dict.pyi',
    'builtins.set': 'set.pyi',
    'builtins.bool': 'bool.pyi',
    'builtins.Exception': 'exception.pyi',
    'builtins.BaseException': 'exception.pyi',
    'builtins.isinstance': 'isinstancelist.pyi',
    'builtins.property': 'property.pyi',
    'builtins.classmethod': 'classmethod.pyi',
}  # type: Final


class SemanticAnalyzerPass2(NodeVisitor[None],
                            SemanticAnalyzerInterface,
                            SemanticAnalyzerPluginInterface):
    """Semantically analyze parsed mypy files.

    The analyzer binds names and does various consistency checks for a
    parse tree. Note that type checking is performed as a separate
    pass.

    This is the second phase of semantic analysis.
    """

    # Module name space
    modules = None  # type: Dict[str, MypyFile]
    # Global name space for current module
    globals = None  # type: SymbolTable
    # Names declared using "global" (separate set for each scope)
    global_decls = None  # type: List[Set[str]]
    # Names declated using "nonlocal" (separate set for each scope)
    nonlocal_decls = None  # type: List[Set[str]]
    # Local names of function scopes; None for non-function scopes.
    locals = None  # type: List[Optional[SymbolTable]]
    # Nested block depths of scopes
    block_depth = None  # type: List[int]
    # TypeInfo of directly enclosing class (or None)
    type = None  # type: Optional[TypeInfo]
    # Stack of outer classes (the second tuple item contains tvars).
    type_stack = None  # type: List[Optional[TypeInfo]]
    # Type variables bound by the current scope, be it class or function
    tvar_scope = None  # type: TypeVarScope
    # Per-module options
    options = None  # type: Options

    # Stack of functions being analyzed
    function_stack = None  # type: List[FuncItem]

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
    _is_typeshed_stub_file = False  # Are we analyzing a typeshed stub file?
    imports = None  # type: Set[str]  # Imported modules (during phase 2 analysis)
    # Note: some imports (and therefore dependencies) might
    # not be found in phase 1, for example due to * imports.
    errors = None  # type: Errors     # Keeps track of generated errors
    plugin = None  # type: Plugin     # Mypy plugin for special casing of library features

    def __init__(self,
                 modules: Dict[str, MypyFile],
                 missing_modules: Set[str],
                 errors: Errors,
                 plugin: Plugin) -> None:
        """Construct semantic analyzer.

        Use lib_path to search for modules, and report analysis errors
        using the Errors instance.
        """
        self.locals = [None]
        self.imports = set()
        self.type = None
        self.type_stack = []
        self.tvar_scope = TypeVarScope()
        self.function_stack = []
        self.block_depth = [0]
        self.loop_depth = 0
        self.errors = errors
        self.modules = modules
        self.msg = MessageBuilder(errors, modules)
        self.missing_modules = missing_modules
        self.postpone_nested_functions_stack = [FUNCTION_BOTH_PHASES]
        self.postponed_functions_stack = []
        self.all_exports = []  # type: List[str]
        # Map from module id to list of explicitly exported names (i.e. names in __all__).
        self.export_map = {}  # type: Dict[str, List[str]]
        self.plugin = plugin
        # If True, process function definitions. If False, don't. This is used
        # for processing module top levels in fine-grained incremental mode.
        self.recurse_into_functions = True
        self.scope = Scope()

    # mypyc doesn't properly handle implementing an abstractproperty
    # with a regular attribute so we make it a property
    @property
    def is_typeshed_stub_file(self) -> bool:
        return self._is_typeshed_stub_file

    def add_plugin_dependency(self, trigger: str, target: Optional[str] = None) -> None:
        """Add dependency from trigger to a target.

        If the target is not given explicitly, use the current target.
        """
        if target is None:
            target = self.scope.current_target()
        self.cur_mod_node.plugin_deps.setdefault(trigger, set()).add(target)

    def visit_file(self, file_node: MypyFile, fnam: str, options: Options,
                   patches: List[Tuple[int, Callable[[], None]]]) -> None:
        """Run semantic analysis phase 2 over a file.

        Add (priority, callback) pairs by mutating the 'patches' list argument. They
        will be called after all semantic analysis phases but before type checking,
        lowest priority values first.
        """
        self.recurse_into_functions = True
        self.options = options
        self.errors.set_file(fnam, file_node.fullname(), scope=self.scope)
        self.cur_mod_node = file_node
        self.cur_mod_id = file_node.fullname()
        self.is_stub_file = fnam.lower().endswith('.pyi')
        self._is_typeshed_stub_file = self.errors.is_typeshed_file(file_node.path)
        self.globals = file_node.names
        self.patches = patches
        self.named_tuple_analyzer = NamedTupleAnalyzer(options, self)
        self.typed_dict_analyzer = TypedDictAnalyzer(options, self, self.msg)
        self.enum_call_analyzer = EnumCallAnalyzer(options, self)
        self.newtype_analyzer = NewTypeAnalyzer(options, self, self.msg)

        with state.strict_optional_set(options.strict_optional):
            if 'builtins' in self.modules:
                self.globals['__builtins__'] = SymbolTableNode(GDEF,
                                                               self.modules['builtins'])

            for name in implicit_module_attrs:
                v = self.globals[name].node
                if isinstance(v, Var):
                    assert v.type is not None, "Type of implicit attribute not set"
                    v.type = self.anal_type(v.type)
                    v.is_ready = True

            defs = file_node.defs
            self.scope.enter_file(file_node.fullname())
            for d in defs:
                self.accept(d)
            self.scope.leave()

            if self.cur_mod_id == 'builtins':
                remove_imported_names_from_symtable(self.globals, 'builtins')
                for alias_name in type_aliases:
                    self.globals.pop(alias_name.split('.')[-1], None)

            if '__all__' in self.globals:
                for name, g in self.globals.items():
                    if name not in self.all_exports:
                        g.module_public = False

            self.export_map[self.cur_mod_id] = self.all_exports
            self.all_exports = []
            del self.options
            del self.patches
            del self.cur_mod_node
            del self.globals

    def refresh_partial(self, node: Union[MypyFile, FuncDef, OverloadedFuncDef],
                        patches: List[Tuple[int, Callable[[], None]]]) -> None:
        """Refresh a stale target in fine-grained incremental mode."""
        self.patches = patches
        if isinstance(node, MypyFile):
            self.refresh_top_level(node)
        else:
            self.recurse_into_functions = True
            self.accept(node)
        del self.patches

    def refresh_top_level(self, file_node: MypyFile) -> None:
        """Reanalyze a stale module top-level in fine-grained incremental mode."""
        self.recurse_into_functions = False
        for d in file_node.defs:
            self.accept(d)

    @contextmanager
    def file_context(self, file_node: MypyFile, fnam: str, options: Options,
                     active_type: Optional[TypeInfo],
                     scope: Optional[Scope] = None) -> Iterator[None]:
        # TODO: Use this above in visit_file
        scope = scope or self.scope
        self.options = options
        self.errors.set_file(fnam, file_node.fullname(), scope=scope)
        self.cur_mod_node = file_node
        self.cur_mod_id = file_node.fullname()
        scope.enter_file(self.cur_mod_id)
        self.is_stub_file = fnam.lower().endswith('.pyi')
        self._is_typeshed_stub_file = self.errors.is_typeshed_file(file_node.path)
        self.globals = file_node.names
        self.tvar_scope = TypeVarScope()
        if active_type:
            scope.enter_class(active_type)
            self.enter_class(active_type.defn.info)
            for tvar in active_type.defn.type_vars:
                self.tvar_scope.bind_existing(tvar)

        yield

        if active_type:
            scope.leave()
            self.leave_class()
            self.type = None
        scope.leave()
        del self.options

    def visit_func_def(self, defn: FuncDef) -> None:
        if not self.recurse_into_functions:
            return

        with self.scope.function_scope(defn):
            self._visit_func_def(defn)

    def _visit_func_def(self, defn: FuncDef) -> None:
        phase_info = self.postpone_nested_functions_stack[-1]
        if phase_info != FUNCTION_SECOND_PHASE:
            self.function_stack.append(defn)
            # First phase of analysis for function.
            if not defn._fullname:
                defn._fullname = self.qualified_name(defn.name())
            if defn.type:
                assert isinstance(defn.type, CallableType)
                self.update_function_type_variables(defn.type, defn)
            self.function_stack.pop()

            defn.is_conditional = self.block_depth[-1] > 0

            # TODO(jukka): Figure out how to share the various cases. It doesn't
            #   make sense to have (almost) duplicate code (here and elsewhere) for
            #   3 cases: module-level, class-level and local names. Maybe implement
            #   a common stack of namespaces. As the 3 kinds of namespaces have
            #   different semantics, this wouldn't always work, but it might still
            #   be a win.
            #   Also we can re-use some logic in self.add_symbol().
            if self.is_class_scope():
                # Method definition
                assert self.type is not None, "Type not set at class scope"
                defn.info = self.type
                add_symbol = True
                if not defn.is_decorated and not defn.is_overload:
                    if (defn.name() in self.type.names and
                            self.type.names[defn.name()].node != defn):
                        # Redefinition. Conditional redefinition is okay.
                        n = self.type.names[defn.name()].node
                        if not self.set_original_def(n, defn):
                            self.name_already_defined(defn.name(), defn,
                                                      self.type.names[defn.name()])
                            add_symbol = False
                    if add_symbol:
                        self.type.names[defn.name()] = SymbolTableNode(MDEF, defn)
                if defn.type is not None and defn.name() in ('__init__', '__init_subclass__'):
                    assert isinstance(defn.type, CallableType)
                    if isinstance(defn.type.ret_type, AnyType):
                        defn.type = defn.type.copy_modified(ret_type=NoneTyp())
                self.prepare_method_signature(defn, self.type)
            elif self.is_func_scope():
                # Nested function
                assert self.locals[-1] is not None, "No locals at function scope"
                if not defn.is_decorated and not defn.is_overload:
                    if defn.name() in self.locals[-1]:
                        # Redefinition. Conditional redefinition is okay.
                        n = self.locals[-1][defn.name()].node
                        if not self.set_original_def(n, defn):
                            self.name_already_defined(defn.name(), defn,
                                                      self.locals[-1][defn.name()])
                    else:
                        self.add_local(defn, defn)
            else:
                # Top-level function
                if not defn.is_decorated and not defn.is_overload:
                    symbol = self.globals[defn.name()]
                    if isinstance(symbol.node, FuncDef) and symbol.node != defn:
                        # This is redefinition. Conditional redefinition is okay.
                        if not self.set_original_def(symbol.node, defn):
                            # Report error.
                            self.check_no_global(defn.name(), defn, True)

            # Analyze function signature and initializers in the first phase
            # (at least this mirrors what happens at runtime).
            with self.tvar_scope_frame(self.tvar_scope.method_frame()):
                if defn.type:
                    self.check_classvar_in_signature(defn.type)
                    assert isinstance(defn.type, CallableType)
                    # Signature must be analyzed in the surrounding scope so that
                    # class-level imported names and type variables are in scope.
                    analyzer = self.type_analyzer()
                    defn.type = analyzer.visit_callable_type(defn.type, nested=False)
                    self.add_type_alias_deps(analyzer.aliases_used)
                    self.check_function_signature(defn)
                    if isinstance(defn, FuncDef):
                        assert isinstance(defn.type, CallableType)
                        defn.type = set_callable_name(defn.type, defn)
                for arg in defn.arguments:
                    if arg.initializer:
                        arg.initializer.accept(self)

            if phase_info == FUNCTION_FIRST_PHASE_POSTPONE_SECOND:
                # Postpone this function (for the second phase).
                self.postponed_functions_stack[-1].append(defn)
                return
        if phase_info != FUNCTION_FIRST_PHASE_POSTPONE_SECOND:
            # Second phase of analysis for function.
            self.analyze_function(defn)
            if defn.is_coroutine and isinstance(defn.type, CallableType):
                if defn.is_async_generator:
                    # Async generator types are handled elsewhere
                    pass
                else:
                    # A coroutine defined as `async def foo(...) -> T: ...`
                    # has external return type `Coroutine[Any, Any, T]`.
                    any_type = AnyType(TypeOfAny.special_form)
                    ret_type = self.named_type_or_none('typing.Coroutine',
                        [any_type, any_type, defn.type.ret_type])
                    assert ret_type is not None, "Internal error: typing.Coroutine not found"
                    defn.type = defn.type.copy_modified(ret_type=ret_type)

    def prepare_method_signature(self, func: FuncDef, info: TypeInfo) -> None:
        """Check basic signature validity and tweak annotation of self/cls argument."""
        # Only non-static methods are special.
        functype = func.type
        if not func.is_static:
            if not func.arguments:
                self.fail('Method must have at least one argument', func)
            elif isinstance(functype, CallableType):
                self_type = functype.arg_types[0]
                if isinstance(self_type, AnyType):
                    leading_type = fill_typevars(info)  # type: Type
                    if func.is_class or func.name() in ('__new__', '__init_subclass__'):
                        leading_type = self.class_type(leading_type)
                    func.type = replace_implicit_first_type(functype, leading_type)

    def set_original_def(self, previous: Optional[Node], new: FuncDef) -> bool:
        """If 'new' conditionally redefine 'previous', set 'previous' as original

        We reject straight redefinitions of functions, as they are usually
        a programming error. For example:

        . def f(): ...
        . def f(): ...  # Error: 'f' redefined
        """
        if isinstance(previous, (FuncDef, Var, Decorator)) and new.is_conditional:
            new.original_def = previous
            return True
        else:
            return False

    def update_function_type_variables(self, fun_type: CallableType, defn: FuncItem) -> None:
        """Make any type variables in the signature of defn explicit.

        Update the signature of defn to contain type variable definitions
        if defn is generic.
        """
        with self.tvar_scope_frame(self.tvar_scope.method_frame()):
            a = self.type_analyzer()
            fun_type.variables = a.bind_function_type_variables(fun_type, defn)

    def visit_overloaded_func_def(self, defn: OverloadedFuncDef) -> None:
        if not self.recurse_into_functions:
            return
        # NB: Since _visit_overloaded_func_def will call accept on the
        # underlying FuncDefs, the function might get entered twice.
        # This is fine, though, because only the outermost function is
        # used to compute targets.
        with self.scope.function_scope(defn):
            self._visit_overloaded_func_def(defn)

    def _visit_overloaded_func_def(self, defn: OverloadedFuncDef) -> None:
        # OverloadedFuncDef refers to any legitimate situation where you have
        # more than one declaration for the same function in a row.  This occurs
        # with a @property with a setter or a deleter, and for a classic
        # @overload.

        defn._fullname = self.qualified_name(defn.name())

        first_item = defn.items[0]
        first_item.is_overload = True
        first_item.accept(self)

        if isinstance(first_item, Decorator) and first_item.func.is_property:
            # This is a property.
            first_item.func.is_overload = True
            self.analyze_property_with_multi_part_definition(defn)
            typ = function_type(first_item.func, self.builtin_type('builtins.function'))
            assert isinstance(typ, CallableType)
            types = [typ]
        else:
            # This is an a normal overload. Find the item signatures, the
            # implementation (if outside a stub), and any missing @overload
            # decorators.
            types, impl, non_overload_indexes = self.find_overload_sigs_and_impl(defn)
            defn.impl = impl
            if non_overload_indexes:
                self.handle_missing_overload_decorators(defn, non_overload_indexes,
                                                        some_overload_decorators=len(types) > 0)
            # If we found an implementation, remove it from the overload item list,
            # as it's special.
            if impl is not None:
                assert impl is defn.items[-1]
                defn.items = defn.items[:-1]
            elif not non_overload_indexes:
                self.handle_missing_overload_implementation(defn)

        if types:
            defn.type = Overloaded(types)
            defn.type.line = defn.line

        if not defn.items:
            # It was not a real overload after all, but function redefinition. We've
            # visited the redefinition(s) already.
            return

        # We know this is an overload def. Infer properties and perform some checks.
        self.process_final_in_overload(defn)
        self.process_static_or_class_method_in_overload(defn)

        if self.type and not self.is_func_scope():
            self.type.names[defn.name()] = SymbolTableNode(MDEF, defn)
            defn.info = self.type
        elif self.is_func_scope():
            self.add_local(defn, defn)

    def find_overload_sigs_and_impl(
            self,
            defn: OverloadedFuncDef) -> Tuple[List[CallableType],
                                              Optional[OverloadPart],
                                              List[int]]:
        """Find overload signatures, the implementation, and items with missing @overload.

        Assume that the first was already analyzed. As a side effect:
        analyzes remaining items and updates 'is_overload' flags.
        """
        types = []
        non_overload_indexes = []
        impl = None  # type: Optional[OverloadPart]
        for i, item in enumerate(defn.items):
            if i != 0:
                # Assume that the first item was already visited
                item.is_overload = True
                item.accept(self)
            # TODO: support decorated overloaded functions properly
            if isinstance(item, Decorator):
                callable = function_type(item.func, self.builtin_type('builtins.function'))
                assert isinstance(callable, CallableType)
                if not any(refers_to_fullname(dec, 'typing.overload')
                           for dec in item.decorators):
                    if i == len(defn.items) - 1 and not self.is_stub_file:
                        # Last item outside a stub is impl
                        impl = item
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
                    impl = item
                else:
                    non_overload_indexes.append(i)
        return types, impl, non_overload_indexes

    def handle_missing_overload_decorators(self,
                                           defn: OverloadedFuncDef,
                                           non_overload_indexes: List[int],
                                           some_overload_decorators: bool) -> None:
        """Generate errors for overload items without @overload.

        Side effect: remote non-overload items.
        """
        if some_overload_decorators:
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
                self.name_already_defined(defn.name(), defn.items[idx], defn.items[0])
            if defn.impl:
                self.name_already_defined(defn.name(), defn.impl, defn.items[0])
        # Remove the non-overloads
        for idx in reversed(non_overload_indexes):
            del defn.items[idx]

    def handle_missing_overload_implementation(self, defn: OverloadedFuncDef) -> None:
        """Generate error about missing overload implementation (only if needed)."""
        if not self.is_stub_file:
            if self.type and self.type.is_protocol and not self.is_func_scope():
                # An overloded protocol method doesn't need an implementation.
                for item in defn.items:
                    if isinstance(item, Decorator):
                        item.func.is_abstract = True
                    else:
                        item.is_abstract = True
            else:
                self.fail(
                    "An overloaded function outside a stub file must have an implementation",
                    defn)

    def process_final_in_overload(self, defn: OverloadedFuncDef) -> None:
        """Detect the @final status of an overloaded function (and perform checks)."""
        # If the implementation is marked as @final (or the first overload in
        # stubs), then the whole overloaded definition if @final.
        if any(item.is_final for item in defn.items):
            # We anyway mark it as final because it was probably the intention.
            defn.is_final = True
            # Only show the error once per overload
            bad_final = next(ov for ov in defn.items if ov.is_final)
            if not self.is_stub_file:
                self.fail("@final should be applied only to overload implementation",
                          bad_final)
            elif any(item.is_final for item in defn.items[1:]):
                bad_final = next(ov for ov in defn.items[1:] if ov.is_final)
                self.fail("In a stub file @final must be applied only to the first overload",
                          bad_final)
        if defn.impl is not None and defn.impl.is_final:
            defn.is_final = True

    def process_static_or_class_method_in_overload(self, defn: OverloadedFuncDef) -> None:
        class_status = []
        static_status = []
        for item in defn.items:
            if isinstance(item, Decorator):
                inner = item.func
            elif isinstance(item, FuncDef):
                inner = item
            else:
                assert False, "The 'item' variable is an unexpected type: {}".format(type(item))
            class_status.append(inner.is_class)
            static_status.append(inner.is_static)

        if defn.impl is not None:
            if isinstance(defn.impl, Decorator):
                inner = defn.impl.func
            elif isinstance(defn.impl, FuncDef):
                inner = defn.impl
            else:
                assert False, "Unexpected impl type: {}".format(type(defn.impl))
            class_status.append(inner.is_class)
            static_status.append(inner.is_static)

        if len(set(class_status)) != 1:
            self.msg.overload_inconsistently_applies_decorator('classmethod', defn)
        elif len(set(static_status)) != 1:
            self.msg.overload_inconsistently_applies_decorator('staticmethod', defn)
        else:
            defn.is_class = class_status[0]
            defn.is_static = static_status[0]

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
            else:
                self.fail("Decorated property not supported", item)
            if isinstance(item, Decorator):
                item.func.accept(self)

    def analyze_function(self, defn: FuncItem) -> None:
        is_method = self.is_class_scope()
        with self.tvar_scope_frame(self.tvar_scope.method_frame()):
            # Bind the type variables again to visit the body.
            if defn.type:
                a = self.type_analyzer()
                a.bind_function_type_variables(cast(CallableType, defn.type), defn)
            self.function_stack.append(defn)
            self.enter()
            for arg in defn.arguments:
                self.add_local(arg.variable, defn)

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

            self.leave()
            self.function_stack.pop()

    def check_classvar_in_signature(self, typ: Type) -> None:
        if isinstance(typ, Overloaded):
            for t in typ.items():  # type: Type
                self.check_classvar_in_signature(t)
            return
        if not isinstance(typ, CallableType):
            return
        for t in typ.arg_types + [typ.ret_type]:
            if self.is_classvar(t):
                self.fail_invalid_classvar(t)
                # Show only one error per signature
                break

    def check_function_signature(self, fdef: FuncItem) -> None:
        sig = fdef.type
        assert isinstance(sig, CallableType)
        if len(sig.arg_types) < len(fdef.arguments):
            self.fail('Type signature has too few arguments', fdef)
            # Add dummy Any arguments to prevent crashes later.
            num_extra_anys = len(fdef.arguments) - len(sig.arg_types)
            extra_anys = [AnyType(TypeOfAny.from_error)] * num_extra_anys
            sig.arg_types.extend(extra_anys)
        elif len(sig.arg_types) > len(fdef.arguments):
            self.fail('Type signature has too many arguments', fdef, blocker=True)

    def visit_class_def(self, defn: ClassDef) -> None:
        with self.scope.class_scope(defn.info):
            with self.tvar_scope_frame(self.tvar_scope.class_frame()):
                self.analyze_class(defn)

    def analyze_class(self, defn: ClassDef) -> None:
        is_protocol = self.detect_protocol_base(defn)
        self.update_metaclass(defn)
        self.clean_up_bases_and_infer_type_variables(defn)
        self.analyze_class_keywords(defn)
        if self.typed_dict_analyzer.analyze_typeddict_classdef(defn):
            return
        if self.analyze_namedtuple_classdef(defn):
            return
        self.setup_class_def_analysis(defn)
        self.analyze_base_classes(defn)
        defn.info.is_protocol = is_protocol
        self.analyze_metaclass(defn)
        defn.info.runtime_protocol = False
        for decorator in defn.decorators:
            self.analyze_class_decorator(defn, decorator)
        self.analyze_class_body_common(defn)
        self.setup_type_promotion(defn)

    def analyze_class_body_common(self, defn: ClassDef) -> None:
        """Parts of class body analysis that are common to all kinds of class defs."""
        self.enter_class(defn.info)
        defn.defs.accept(self)
        self.calculate_abstract_status(defn.info)
        self.apply_class_plugin_hooks(defn)
        self.leave_class()

    def analyze_namedtuple_classdef(self, defn: ClassDef) -> bool:
        """Analyze class-based named tuple if the NamedTuple base class is present.

        TODO: Move this to NamedTupleAnalyzer?

        Return True only if the class is a NamedTuple class.
        """
        named_tuple_info = self.named_tuple_analyzer.analyze_namedtuple_classdef(defn)
        if named_tuple_info is None:
            return False
        # Temporarily clear the names dict so we don't get errors about duplicate names
        # that were already set in build_namedtuple_typeinfo.
        nt_names = named_tuple_info.names
        named_tuple_info.names = SymbolTable()

        self.analyze_class_body_common(defn)

        # Make sure we didn't use illegal names, then reset the names in the typeinfo.
        for prohibited in NAMEDTUPLE_PROHIBITED_NAMES:
            if prohibited in named_tuple_info.names:
                if nt_names.get(prohibited) is named_tuple_info.names[prohibited]:
                    continue
                ctx = named_tuple_info.names[prohibited].node
                assert ctx is not None
                self.fail('Cannot overwrite NamedTuple attribute "{}"'.format(prohibited),
                          ctx)

        # Restore the names in the original symbol table. This ensures that the symbol
        # table contains the field objects created by build_namedtuple_typeinfo. Exclude
        # __doc__, which can legally be overwritten by the class.
        named_tuple_info.names.update({
            key: value for key, value in nt_names.items()
            if key not in named_tuple_info.names or key != '__doc__'
        })
        return True

    def apply_class_plugin_hooks(self, defn: ClassDef) -> None:
        """Apply a plugin hook that may infer a more precise definition for a class."""
        def get_fullname(expr: Expression) -> Optional[str]:
            if isinstance(expr, CallExpr):
                return get_fullname(expr.callee)
            elif isinstance(expr, IndexExpr):
                return get_fullname(expr.base)
            elif isinstance(expr, RefExpr):
                if expr.fullname:
                    return expr.fullname
                # If we don't have a fullname look it up. This happens because base classes are
                # analyzed in a different manner (see exprtotype.py) and therefore those AST
                # nodes will not have full names.
                sym = self.lookup_type_node(expr)
                if sym:
                    return sym.fullname
            return None

        for decorator in defn.decorators:
            decorator_name = get_fullname(decorator)
            if decorator_name:
                hook = self.plugin.get_class_decorator_hook(decorator_name)
                if hook:
                    hook(ClassDefContext(defn, decorator, self))

        if defn.metaclass:
            metaclass_name = get_fullname(defn.metaclass)
            if metaclass_name:
                hook = self.plugin.get_metaclass_hook(metaclass_name)
                if hook:
                    hook(ClassDefContext(defn, defn.metaclass, self))

        for base_expr in defn.base_type_exprs:
            base_name = get_fullname(base_expr)
            if base_name:
                hook = self.plugin.get_base_class_hook(base_name)
                if hook:
                    hook(ClassDefContext(defn, base_expr, self))

    def analyze_class_keywords(self, defn: ClassDef) -> None:
        for value in defn.keywords.values():
            value.accept(self)

    def enter_class(self, info: TypeInfo) -> None:
        # Remember previous active class
        self.type_stack.append(self.type)
        self.locals.append(None)  # Add class scope
        self.block_depth.append(-1)  # The class body increments this to 0
        self.postpone_nested_functions_stack.append(FUNCTION_BOTH_PHASES)
        self.type = info

    def leave_class(self) -> None:
        """ Restore analyzer state. """
        self.postpone_nested_functions_stack.pop()
        self.block_depth.pop()
        self.locals.pop()
        self.type = self.type_stack.pop()

    def analyze_class_decorator(self, defn: ClassDef, decorator: Expression) -> None:
        decorator.accept(self)
        if isinstance(decorator, RefExpr):
            if decorator.fullname in ('typing.runtime', 'typing_extensions.runtime'):
                if defn.info.is_protocol:
                    defn.info.runtime_protocol = True
                else:
                    self.fail('@runtime can only be used with protocol classes', defn)
            elif decorator.fullname in ('typing.final',
                                        'typing_extensions.final'):
                defn.info.is_final = True

    def calculate_abstract_status(self, typ: TypeInfo) -> None:
        """Calculate abstract status of a class.

        Set is_abstract of the type to True if the type has an unimplemented
        abstract attribute.  Also compute a list of abstract attributes.
        """
        concrete = set()  # type: Set[str]
        abstract = []  # type: List[str]
        abstract_in_this_class = []  # type: List[str]
        for base in typ.mro:
            for name, symnode in base.names.items():
                node = symnode.node
                if isinstance(node, OverloadedFuncDef):
                    # Unwrap an overloaded function definition. We can just
                    # check arbitrarily the first overload item. If the
                    # different items have a different abstract status, there
                    # should be an error reported elsewhere.
                    func = node.items[0]  # type: Optional[Node]
                else:
                    func = node
                if isinstance(func, Decorator):
                    fdef = func.func
                    if fdef.is_abstract and name not in concrete:
                        typ.is_abstract = True
                        abstract.append(name)
                        if base is typ:
                            abstract_in_this_class.append(name)
                elif isinstance(node, Var):
                    if node.is_abstract_var and name not in concrete:
                        typ.is_abstract = True
                        abstract.append(name)
                        if base is typ:
                            abstract_in_this_class.append(name)
                concrete.add(name)
        # In stubs, abstract classes need to be explicitly marked because it is too
        # easy to accidentally leave a concrete class abstract by forgetting to
        # implement some methods.
        typ.abstract_attributes = sorted(abstract)
        if not self.is_stub_file:
            return
        if (typ.declared_metaclass and typ.declared_metaclass.type.fullname() == 'abc.ABCMeta'):
            return
        if typ.is_protocol:
            return
        if abstract and not abstract_in_this_class:
            attrs = ", ".join('"{}"'.format(attr) for attr in sorted(abstract))
            self.fail("Class {} has abstract attributes {}".format(typ.fullname(), attrs), typ)
            self.note("If it is meant to be abstract, add 'abc.ABCMeta' as an explicit metaclass",
                      typ)

    def setup_type_promotion(self, defn: ClassDef) -> None:
        """Setup extra, ad-hoc subtyping relationships between classes (promotion).

        This includes things like 'int' being compatible with 'float'.
        """
        promote_target = None  # type: Optional[Type]
        for decorator in defn.decorators:
            if isinstance(decorator, CallExpr):
                analyzed = decorator.analyzed
                if isinstance(analyzed, PromoteExpr):
                    # _promote class decorator (undocumented feature).
                    promote_target = analyzed.type
        if not promote_target:
            promotions = (TYPE_PROMOTIONS_PYTHON3 if self.options.python_version[0] >= 3
                          else TYPE_PROMOTIONS_PYTHON2)
            if defn.fullname in promotions:
                promote_target = self.named_type_or_none(promotions[defn.fullname])
        defn.info._promote = promote_target

    def detect_protocol_base(self, defn: ClassDef) -> bool:
        for base_expr in defn.base_type_exprs:
            try:
                base = expr_to_unanalyzed_type(base_expr)
            except TypeTranslationError:
                continue  # This will be reported later
            if not isinstance(base, UnboundType):
                continue
            sym = self.lookup_qualified(base.name, base)
            if sym is None or sym.node is None:
                continue
            if sym.node.fullname() in ('typing.Protocol', 'typing_extensions.Protocol'):
                return True
        return False

    def clean_up_bases_and_infer_type_variables(self, defn: ClassDef) -> None:
        """Remove extra base classes such as Generic and infer type vars.

        For example, consider this class:

        . class Foo(Bar, Generic[T]): ...

        Now we will remove Generic[T] from bases of Foo and infer that the
        type variable 'T' is a type argument of Foo.

        Note that this is performed *before* semantic analysis.
        """
        removed = []  # type: List[int]
        declared_tvars = []  # type: TypeVarList
        for i, base_expr in enumerate(defn.base_type_exprs):
            self.analyze_type_expr(base_expr)

            try:
                base = expr_to_unanalyzed_type(base_expr)
            except TypeTranslationError:
                # This error will be caught later.
                continue
            tvars = self.analyze_typevar_declaration(base)
            if tvars is not None:
                if declared_tvars:
                    self.fail('Only single Generic[...] or Protocol[...] can be in bases', defn)
                removed.append(i)
                declared_tvars.extend(tvars)
            if isinstance(base, UnboundType):
                sym = self.lookup_qualified(base.name, base)
                if sym is not None and sym.node is not None:
                    if (sym.node.fullname() in ('typing.Protocol',
                                                'typing_extensions.Protocol') and
                            i not in removed):
                        # also remove bare 'Protocol' bases
                        removed.append(i)

        all_tvars = self.get_all_bases_tvars(defn, removed)
        if declared_tvars:
            if len(remove_dups(declared_tvars)) < len(declared_tvars):
                self.fail("Duplicate type variables in Generic[...] or Protocol[...]", defn)
            declared_tvars = remove_dups(declared_tvars)
            if not set(all_tvars).issubset(set(declared_tvars)):
                self.fail("If Generic[...] or Protocol[...] is present"
                          " it should list all type variables", defn)
                # In case of error, Generic tvars will go first
                declared_tvars = remove_dups(declared_tvars + all_tvars)
        else:
            declared_tvars = all_tvars
        if declared_tvars:
            if defn.info:
                defn.info.type_vars = [name for name, _ in declared_tvars]
        for i in reversed(removed):
            defn.removed_base_type_exprs.append(defn.base_type_exprs[i])
            del defn.base_type_exprs[i]
        tvar_defs = []  # type: List[TypeVarDef]
        for name, tvar_expr in declared_tvars:
            tvar_def = self.tvar_scope.bind_new(name, tvar_expr)
            tvar_defs.append(tvar_def)
        defn.type_vars = tvar_defs

    def analyze_typevar_declaration(self, t: Type) -> Optional[TypeVarList]:
        if not isinstance(t, UnboundType):
            return None
        unbound = t
        sym = self.lookup_qualified(unbound.name, unbound)
        if sym is None or sym.node is None:
            return None
        if (sym.node.fullname() == 'typing.Generic' or
                sym.node.fullname() == 'typing.Protocol' and t.args or
                sym.node.fullname() == 'typing_extensions.Protocol' and t.args):
            tvars = []  # type: TypeVarList
            for arg in unbound.args:
                tvar = self.analyze_unbound_tvar(arg)
                if tvar:
                    tvars.append(tvar)
                else:
                    self.fail('Free type variable expected in %s[...]' %
                              sym.node.name(), t)
            return tvars
        return None

    def analyze_unbound_tvar(self, t: Type) -> Optional[Tuple[str, TypeVarExpr]]:
        if not isinstance(t, UnboundType):
            return None
        unbound = t
        sym = self.lookup_qualified(unbound.name, unbound)
        if sym is None or not isinstance(sym.node, TypeVarExpr):
            return None
        elif sym.fullname and not self.tvar_scope.allow_binding(sym.fullname):
            # It's bound by our type variable scope
            return None
        else:
            assert isinstance(sym.node, TypeVarExpr)
            return unbound.name, sym.node

    def get_all_bases_tvars(self, defn: ClassDef, removed: List[int]) -> TypeVarList:
        tvars = []  # type: TypeVarList
        for i, base_expr in enumerate(defn.base_type_exprs):
            if i not in removed:
                try:
                    base = expr_to_unanalyzed_type(base_expr)
                except TypeTranslationError:
                    # This error will be caught later.
                    continue
                base_tvars = base.accept(TypeVariableQuery(self.lookup_qualified, self.tvar_scope))
                tvars.extend(base_tvars)
        return remove_dups(tvars)

    def setup_class_def_analysis(self, defn: ClassDef) -> None:
        """Prepare for the analysis of a class definition."""
        if not defn.info:
            defn.info = TypeInfo(SymbolTable(), defn, self.cur_mod_id)
            defn.info._fullname = defn.info.name()
        if self.is_func_scope() or self.type:
            kind = MDEF
            if self.is_nested_within_func_scope():
                kind = LDEF
            node = SymbolTableNode(kind, defn.info)
            self.add_symbol(defn.name, node, defn)
            if kind == LDEF:
                # We need to preserve local classes, let's store them
                # in globals under mangled unique names
                #
                # TODO: Putting local classes into globals breaks assumptions in fine-grained
                #     incremental mode and we should avoid it.
                if '@' not in defn.info._fullname:
                    local_name = defn.info._fullname + '@' + str(defn.line)
                    defn.info._fullname = self.cur_mod_id + '.' + local_name
                else:
                    # Preserve name from previous fine-grained incremental run.
                    local_name = defn.info._fullname
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
                if isinstance(base_expr, CallExpr):
                    defn.analyzed = NamedTupleExpr(base.fallback.type)
                    defn.analyzed.line = defn.line
                    defn.analyzed.column = defn.column
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
            if self.options.disallow_any_unimported and has_any_from_unimported_type(base):
                if isinstance(base_expr, (NameExpr, MemberExpr)):
                    prefix = "Base type {}".format(base_expr.name)
                else:
                    prefix = "Base type"
                self.msg.unimported_type_becomes_any(prefix, base, base_expr)
            check_for_explicit_any(base, self.options, self.is_typeshed_stub_file, self.msg,
                                   context=base_expr)

        # Add 'object' as implicit base if there is no other base class.
        if (not base_types and defn.fullname != 'builtins.object'):
            base_types.append(self.object_type())

        info.bases = base_types

        # Calculate the MRO. It might be incomplete at this point if
        # the bases of defn include classes imported from other
        # modules in an import loop. We'll recompute it in SemanticAnalyzerPass3.
        if not self.verify_base_classes(defn):
            # Give it an MRO consisting of just the class itself and object.
            defn.info.mro = [defn.info, self.object_type().type]
            return
        # TODO: Ideally we should move MRO calculation to a later stage, but this is
        # not easy, see issue #5536.
        self.calculate_class_mro(defn, self.object_type)

    def calculate_class_mro(self, defn: ClassDef,
                            obj_type: Optional[Callable[[], Instance]] = None) -> None:
        """Calculate method resolution order for a class.

        `obj_type` may be omitted in the third pass when all classes are already analyzed.
        It exists just to fill in empty base class list during second pass in case of
        an import cycle.
        """
        try:
            calculate_mro(defn.info, obj_type)
        except MroError:
            self.fail_blocker('Cannot determine consistent method resolution '
                              'order (MRO) for "%s"' % defn.name, defn)
            defn.info.mro = []
        # Allow plugins to alter the MRO to handle the fact that `def mro()`
        # on metaclasses permits MRO rewriting.
        if defn.fullname:
            hook = self.plugin.get_customize_class_mro_hook(defn.fullname)
            if hook:
                hook(ClassDefContext(defn, Expression(), self))

    def update_metaclass(self, defn: ClassDef) -> None:
        """Lookup for special metaclass declarations, and update defn fields accordingly.

        * __metaclass__ attribute in Python 2
        * six.with_metaclass(M, B1, B2, ...)
        * @six.add_metaclass(M)
        """

        # Look for "__metaclass__ = <metaclass>" in Python 2
        python2_meta_expr = None  # type: Optional[Expression]
        if self.options.python_version[0] == 2:
            for body_node in defn.defs.body:
                if isinstance(body_node, ClassDef) and body_node.name == "__metaclass__":
                    self.fail("Metaclasses defined as inner classes are not supported", body_node)
                    break
                elif isinstance(body_node, AssignmentStmt) and len(body_node.lvalues) == 1:
                    lvalue = body_node.lvalues[0]
                    if isinstance(lvalue, NameExpr) and lvalue.name == "__metaclass__":
                        python2_meta_expr = body_node.rvalue

        # Look for six.with_metaclass(M, B1, B2, ...)
        with_meta_expr = None  # type: Optional[Expression]
        if len(defn.base_type_exprs) == 1:
            base_expr = defn.base_type_exprs[0]
            if isinstance(base_expr, CallExpr) and isinstance(base_expr.callee, RefExpr):
                base_expr.callee.accept(self)
                if (base_expr.callee.fullname == 'six.with_metaclass'
                        and len(base_expr.args) >= 1
                        and all(kind == ARG_POS for kind in base_expr.arg_kinds)):
                    with_meta_expr = base_expr.args[0]
                    defn.base_type_exprs = base_expr.args[1:]

        # Look for @six.add_metaclass(M)
        add_meta_expr = None  # type: Optional[Expression]
        for dec_expr in defn.decorators:
            if isinstance(dec_expr, CallExpr) and isinstance(dec_expr.callee, RefExpr):
                dec_expr.callee.accept(self)
                if (dec_expr.callee.fullname == 'six.add_metaclass'
                    and len(dec_expr.args) == 1
                        and dec_expr.arg_kinds[0] == ARG_POS):
                    add_meta_expr = dec_expr.args[0]
                    break

        metas = {defn.metaclass, python2_meta_expr, with_meta_expr, add_meta_expr} - {None}
        if len(metas) == 0:
            return
        if len(metas) > 1:
            self.fail("Multiple metaclass definitions", defn)
            return
        defn.metaclass = metas.pop()

    def expr_to_analyzed_type(self, expr: Expression, report_invalid_types: bool = True) -> Type:
        if isinstance(expr, CallExpr):
            expr.accept(self)
            info = self.named_tuple_analyzer.check_namedtuple(expr, None, self.is_func_scope())
            if info is None:
                # Some form of namedtuple is the only valid type that looks like a call
                # expression. This isn't a valid type.
                raise TypeTranslationError()
            assert info.tuple_type, "NamedTuple without tuple type"
            fallback = Instance(info, [])
            return TupleType(info.tuple_type.items, fallback=fallback)
        typ = expr_to_unanalyzed_type(expr)
        return self.anal_type(typ, report_invalid_types=report_invalid_types)

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
        if defn.metaclass:
            metaclass_name = None
            if isinstance(defn.metaclass, NameExpr):
                metaclass_name = defn.metaclass.name
            elif isinstance(defn.metaclass, MemberExpr):
                metaclass_name = get_member_expr_fullname(defn.metaclass)
            if metaclass_name is None:
                self.fail("Dynamic metaclass not supported for '%s'" % defn.name, defn.metaclass)
                return
            sym = self.lookup_qualified(metaclass_name, defn.metaclass)
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
                self.fail("Invalid metaclass '%s'" % metaclass_name, defn.metaclass)
                return
            if not sym.node.is_metaclass():
                self.fail("Metaclasses not inheriting from 'type' are not supported",
                          defn.metaclass)
                return
            inst = fill_typevars(sym.node)
            assert isinstance(inst, Instance)
            defn.info.declared_metaclass = inst
        defn.info.metaclass_type = defn.info.calculate_metaclass_type()
        if any(info.is_protocol for info in defn.info.mro):
            if (not defn.info.metaclass_type or
                    defn.info.metaclass_type.type.fullname() == 'builtins.type'):
                # All protocols and their subclasses have ABCMeta metaclass by default.
                # TODO: add a metaclass conflict check if there is another metaclass.
                abc_meta = self.named_type_or_none('abc.ABCMeta', [])
                if abc_meta is not None:  # May be None in tests with incomplete lib-stub.
                    defn.info.metaclass_type = abc_meta
        if defn.info.metaclass_type is None:
            # Inconsistency may happen due to multiple baseclasses even in classes that
            # do not declare explicit metaclass, but it's harder to catch at this stage
            if defn.metaclass is not None:
                self.fail("Inconsistent metaclass structure for '%s'" % defn.name, defn)
        else:
            if defn.info.metaclass_type.type.has_base('enum.EnumMeta'):
                defn.info.is_enum = True
                if defn.type_vars:
                    self.fail("Enum class cannot be generic", defn)

    def object_type(self) -> Instance:
        return self.named_type('__builtins__.object')

    def str_type(self) -> Instance:
        return self.named_type('__builtins__.str')

    def class_type(self, self_type: Type) -> Type:
        return TypeType.make_normalized(self_type)

    def named_type(self, qualified_name: str, args: Optional[List[Type]] = None) -> Instance:
        sym = self.lookup_qualified(qualified_name, Context())
        assert sym, "Internal error: attempted to construct unknown type"
        node = sym.node
        assert isinstance(node, TypeInfo)
        if args:
            # TODO: assert len(args) == len(node.defn.type_vars)
            return Instance(node, args)
        return Instance(node, [AnyType(TypeOfAny.special_form)] * len(node.defn.type_vars))

    def named_type_or_none(self, qualified_name: str,
                           args: Optional[List[Type]] = None) -> Optional[Instance]:
        sym = self.lookup_fully_qualified_or_none(qualified_name)
        if not sym:
            return None
        node = sym.node
        if isinstance(node, TypeAlias):
            assert isinstance(node.target, Instance)
            node = node.target.type
        assert isinstance(node, TypeInfo), node
        if args is not None:
            # TODO: assert len(args) == len(node.defn.type_vars)
            return Instance(node, args)
        return Instance(node, [AnyType(TypeOfAny.unannotated)] * len(node.defn.type_vars))

    def visit_import(self, i: Import) -> None:
        for id, as_id in i.ids:
            if as_id is not None:
                self.add_module_symbol(id, as_id, module_public=True, context=i)
            else:
                # Modules imported in a stub file without using 'as x' won't get exported
                module_public = not self.is_stub_file
                base = id.split('.')[0]
                self.add_module_symbol(base, base, module_public=module_public,
                                       context=i, module_hidden=not module_public)
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
            if parent_mod and self.allow_patching(parent_mod, child):
                child_mod = self.modules.get(id)
                if child_mod:
                    sym = SymbolTableNode(GDEF, child_mod,
                                          module_public=module_public,
                                          no_serialize=True)
                else:
                    # Construct a dummy Var with Any type.
                    any_type = AnyType(TypeOfAny.from_unimported_type,
                                       missing_import_name=id)
                    var = Var(child, any_type)
                    var._fullname = child
                    var.is_ready = True
                    var.is_suppressed_import = True
                    sym = SymbolTableNode(GDEF, var,
                                          module_public=module_public,
                                          no_serialize=True)
                parent_mod.names[child] = sym
            id = parent

    def allow_patching(self, parent_mod: MypyFile, child: str) -> bool:
        if child not in parent_mod.names:
            return True
        node = parent_mod.names[child].node
        if isinstance(node, Var) and node.is_suppressed_import:
            return True
        return False

    def add_module_symbol(self, id: str, as_id: str, module_public: bool,
                          context: Context, module_hidden: bool = False) -> None:
        """Add symbol that is a reference to a module object."""
        if id in self.modules:
            m = self.modules[id]
            kind = self.current_symbol_kind()
            self.add_symbol(as_id, SymbolTableNode(kind, m,
                                                   module_public=module_public,
                                                   module_hidden=module_hidden), context)
        else:
            self.add_unknown_symbol(as_id, context, is_import=True, target_name=id)

    def visit_import_from(self, imp: ImportFrom) -> None:
        import_id = self.correct_relative_import(imp)
        self.add_submodules_to_parent_modules(import_id, True)
        module = self.modules.get(import_id)
        for id, as_id in imp.names:
            node = module.names.get(id) if module else None
            node = self.dereference_module_cross_ref(node)

            missing = False
            possible_module_id = import_id + '.' + id

            # If the module does not contain a symbol with the name 'id',
            # try checking if it's a module instead.
            if not node or node.kind == UNBOUND_IMPORTED:
                mod = self.modules.get(possible_module_id)
                if mod is not None:
                    kind = self.current_symbol_kind()
                    node = SymbolTableNode(kind, mod)
                    self.add_submodules_to_parent_modules(possible_module_id, True)
                elif possible_module_id in self.missing_modules:
                    missing = True
            # If it is still not resolved, check for a module level __getattr__
            if (module and not node and (module.is_stub or self.options.python_version >= (3, 7))
                    and '__getattr__' in module.names):
                name = as_id if as_id else id
                if self.type:
                    fullname = self.type.fullname() + "." + name
                else:
                    fullname = self.qualified_name(name)
                gvar = self.create_getattr_var(module.names['__getattr__'], name, fullname)
                if gvar:
                    self.add_symbol(name, gvar, imp)
                    continue
            if node and node.kind != UNBOUND_IMPORTED and not node.module_hidden:
                if not node:
                    # Normalization failed because target is not defined. Avoid duplicate
                    # error messages by marking the imported name as unknown.
                    self.add_unknown_symbol(as_id or id, imp, is_import=True)
                    continue
                imported_id = as_id or id
                existing_symbol = self.globals.get(imported_id)
                if existing_symbol:
                    # Import can redefine a variable. They get special treatment.
                    if self.process_import_over_existing_name(
                            imported_id, existing_symbol, node, imp):
                        continue
                # 'from m import x as x' exports x in a stub file.
                module_public = not self.is_stub_file or as_id is not None
                module_hidden = not module_public and possible_module_id not in self.modules
                # NOTE: we take the original node even for final `Var`s. This is to support
                # a common pattern when constants are re-exported (same applies to import *).
                symbol = SymbolTableNode(node.kind, node.node,
                                         module_public=module_public,
                                         module_hidden=module_hidden)
                self.add_symbol(imported_id, symbol, imp)
            elif module and not missing:
                # Missing attribute.
                message = "Module '{}' has no attribute '{}'".format(import_id, id)
                extra = self.undefined_name_extra_info('{}.{}'.format(import_id, id))
                if extra:
                    message += " {}".format(extra)
                self.fail(message, imp)
                self.add_unknown_symbol(as_id or id, imp, is_import=True)

                if import_id == 'typing':
                    # The user probably has a missing definition in a test fixture. Let's verify.
                    fullname = 'builtins.{}'.format(id.lower())
                    if (self.lookup_fully_qualified_or_none(fullname) is None and
                            fullname in SUGGESTED_TEST_FIXTURES):
                        # Yes. Generate a helpful note.
                        self.add_fixture_note(fullname, imp)
            else:
                # Missing module.
                missing_name = import_id + '.' + id
                self.add_unknown_symbol(as_id or id, imp, is_import=True, target_name=missing_name)

    def dereference_module_cross_ref(
            self, node: Optional[SymbolTableNode]) -> Optional[SymbolTableNode]:
        """Dereference cross references to other modules (if any).

        If the node is not a cross reference, return it unmodified.
        """
        seen = set()  # type: Set[str]
        # Continue until we reach a node that's nota cross reference (or until we find
        # nothing).
        while node and isinstance(node.node, ImportedName):
            fullname = node.node.fullname()
            if fullname in self.modules:
                # This is a module reference.
                kind = self.current_symbol_kind()
                return SymbolTableNode(kind, self.modules[fullname])
            if fullname in seen:
                # Looks like a reference cycle. Just break it.
                # TODO: Generate a more specific error message.
                node = None
                break
            node = self.lookup_fully_qualified_or_none(fullname)
            seen.add(fullname)
        return node

    def process_import_over_existing_name(self,
                                          imported_id: str, existing_symbol: SymbolTableNode,
                                          module_symbol: SymbolTableNode,
                                          import_node: ImportBase) -> bool:
        if (existing_symbol.kind in (LDEF, GDEF, MDEF) and
                isinstance(existing_symbol.node, (Var, FuncDef, TypeInfo, Decorator, TypeAlias))):
            # This is a valid import over an existing definition in the file. Construct a dummy
            # assignment that we'll use to type check the import.
            lvalue = NameExpr(imported_id)
            lvalue.kind = existing_symbol.kind
            lvalue.node = existing_symbol.node
            rvalue = NameExpr(imported_id)
            rvalue.kind = module_symbol.kind
            rvalue.node = module_symbol.node
            if isinstance(rvalue.node, TypeAlias):
                # Suppress bogus errors from the dummy assignment if rvalue is an alias.
                # Otherwise mypy may complain that alias is invalid in runtime context.
                rvalue.is_alias_rvalue = True
            assignment = AssignmentStmt([lvalue], rvalue)
            for node in assignment, lvalue, rvalue:
                node.set_line(import_node)
            import_node.assignments.append(assignment)
            return True
        return False

    def add_fixture_note(self, fullname: str, ctx: Context) -> None:
        self.note('Maybe your test fixture does not define "{}"?'.format(fullname), ctx)
        if fullname in SUGGESTED_TEST_FIXTURES:
            self.note(
                'Consider adding [builtins fixtures/{}] to your test description'.format(
                    SUGGESTED_TEST_FIXTURES[fullname]), ctx)

    def correct_relative_import(self, node: Union[ImportFrom, ImportAll]) -> str:
        import_id, ok = correct_relative_import(self.cur_mod_id, node.relative, node.id,
                                                self.cur_mod_node.is_package_init_file())
        if not ok:
            self.fail("Relative import climbs too many namespaces", node)
        return import_id

    def visit_import_all(self, i: ImportAll) -> None:
        i_id = self.correct_relative_import(i)
        if i_id in self.modules:
            m = self.modules[i_id]
            self.add_submodules_to_parent_modules(i_id, True)
            for name, orig_node in m.names.items():
                node = self.dereference_module_cross_ref(orig_node)
                if node is None:
                    continue
                # if '__all__' exists, all nodes not included have had module_public set to
                # False, and we can skip checking '_' because it's been explicitly included.
                if node.module_public and (not name.startswith('_') or '__all__' in m.names):
                    if isinstance(node.node, MypyFile):
                        # Star import of submodule from a package, add it as a dependency.
                        self.imports.add(node.node.fullname())
                    existing_symbol = self.lookup_current_scope(name)
                    if existing_symbol:
                        # Import can redefine a variable. They get special treatment.
                        if self.process_import_over_existing_name(
                                name, existing_symbol, node, i):
                            continue
                    symbol = SymbolTableNode(node.kind, node.node)
                    self.add_symbol(name, symbol, i)
                    i.imported_names.append(name)
        else:
            # Don't add any dummy symbols for 'from x import *' if 'x' is unknown.
            pass

    def add_unknown_symbol(self, name: str, context: Context, is_import: bool = False,
                           target_name: Optional[str] = None) -> None:
        var = Var(name)
        if self.options.logical_deps and target_name is not None:
            # This makes it possible to add logical fine-grained dependencies
            # from a missing module. We can't use this by default, since in a
            # few places we assume that the full name points to a real
            # definition, but this name may point to nothing.
            var._fullname = target_name
        elif self.type:
            var._fullname = self.type.fullname() + "." + name
        else:
            var._fullname = self.qualified_name(name)
        var.is_ready = True
        if is_import:
            any_type = AnyType(TypeOfAny.from_unimported_type, missing_import_name=var._fullname)
        else:
            any_type = AnyType(TypeOfAny.from_error)
        var.type = any_type
        var.is_suppressed_import = is_import
        self.add_symbol(name, SymbolTableNode(GDEF, var), context)

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

    def visit_block_maybe(self, b: Optional[Block]) -> None:
        if b:
            self.visit_block(b)

    def type_analyzer(self, *,
                      tvar_scope: Optional[TypeVarScope] = None,
                      allow_tuple_literal: bool = False,
                      allow_unbound_tvars: bool = False,
                      report_invalid_types: bool = True,
                      third_pass: bool = False) -> TypeAnalyser:
        if tvar_scope is None:
            tvar_scope = self.tvar_scope
        tpan = TypeAnalyser(self,
                            tvar_scope,
                            self.plugin,
                            self.options,
                            self.is_typeshed_stub_file,
                            allow_unbound_tvars=allow_unbound_tvars,
                            allow_tuple_literal=allow_tuple_literal,
                            report_invalid_types=report_invalid_types,
                            allow_unnormalized=self.is_stub_file,
                            third_pass=third_pass)
        tpan.in_dynamic_func = bool(self.function_stack and self.function_stack[-1].is_dynamic())
        tpan.global_scope = not self.type and not self.function_stack
        return tpan

    def anal_type(self, t: Type, *,
                  tvar_scope: Optional[TypeVarScope] = None,
                  allow_tuple_literal: bool = False,
                  allow_unbound_tvars: bool = False,
                  report_invalid_types: bool = True,
                  third_pass: bool = False) -> Type:
        a = self.type_analyzer(tvar_scope=tvar_scope,
                               allow_unbound_tvars=allow_unbound_tvars,
                               allow_tuple_literal=allow_tuple_literal,
                               report_invalid_types=report_invalid_types,
                               third_pass=third_pass)
        typ = t.accept(a)
        self.add_type_alias_deps(a.aliases_used)
        return typ

    def add_type_alias_deps(self, aliases_used: Iterable[str],
                            target: Optional[str] = None) -> None:
        """Add full names of type aliases on which the current node depends.

        This is used by fine-grained incremental mode to re-check the corresponding nodes.
        If `target` is None, then the target node used will be the current scope.
        """
        if not aliases_used:
            # A basic optimization to avoid adding targets with no dependencies to
            # the `alias_deps` dict.
            return
        if target is None:
            target = self.scope.current_target()
        self.cur_mod_node.alias_deps[target].update(aliases_used)

    def visit_assignment_stmt(self, s: AssignmentStmt) -> None:
        s.is_final_def = self.unwrap_final(s)
        self.analyze_lvalues(s)
        s.rvalue.accept(self)
        self.check_final_implicit_def(s)
        self.check_classvar(s)
        self.process_type_annotation(s)
        self.apply_dynamic_class_hook(s)
        self.check_and_set_up_type_alias(s)
        self.newtype_analyzer.process_newtype_declaration(s)
        self.process_typevar_declaration(s)
        self.named_tuple_analyzer.process_namedtuple_definition(s, self.is_func_scope())
        self.typed_dict_analyzer.process_typeddict_definition(s, self.is_func_scope())
        self.enum_call_analyzer.process_enum_call(s, self.is_func_scope())
        self.store_final_status(s)
        if not s.type:
            self.process_module_assignment(s.lvalues, s.rvalue, s)
        self.process__all__(s)

    def analyze_lvalues(self, s: AssignmentStmt) -> None:
        for lval in s.lvalues:
            self.analyze_lvalue(lval,
                                explicit_type=s.type is not None,
                                is_final=s.is_final_def)

    def apply_dynamic_class_hook(self, s: AssignmentStmt) -> None:
        if len(s.lvalues) > 1:
            return
        lval = s.lvalues[0]
        if not isinstance(lval, NameExpr) or not isinstance(s.rvalue, CallExpr):
            return
        call = s.rvalue
        if not isinstance(call.callee, RefExpr):
            return
        fname = call.callee.fullname
        if fname:
            hook = self.plugin.get_dynamic_class_hook(fname)
            if hook:
                hook(DynamicClassDefContext(call, lval.name, self))

    def unwrap_final(self, s: AssignmentStmt) -> bool:
        """Strip Final[...] if present in an assignment.

        This is done to invoke type inference during type checking phase for this
        assignment. Also, Final[...] desn't affect type in any way -- it is rather an
        access qualifier for given `Var`.

        Also perform various consistency checks.

        Returns True if Final[...] was present.
        """
        if not s.type or not self.is_final_type(s.type):
            return False
        assert isinstance(s.type, UnboundType)
        if len(s.type.args) > 1:
            self.fail("Final[...] takes at most one type argument", s.type)
        invalid_bare_final = False
        if not s.type.args:
            s.type = None
            if isinstance(s.rvalue, TempNode) and s.rvalue.no_rhs:
                invalid_bare_final = True
                self.fail("Type in Final[...] can only be omitted if there is an initializer", s)
        else:
            s.type = s.type.args[0]
        if len(s.lvalues) != 1 or not isinstance(s.lvalues[0], RefExpr):
            self.fail("Invalid final declaration", s)
            return False
        lval = s.lvalues[0]
        assert isinstance(lval, RefExpr)
        if self.loop_depth > 0:
            self.fail("Cannot use Final inside a loop", s)
        if self.type and self.type.is_protocol:
            self.msg.protocol_members_cant_be_final(s)
        if (isinstance(s.rvalue, TempNode) and s.rvalue.no_rhs and
                not self.is_stub_file and not self.is_class_scope()):
            if not invalid_bare_final:  # Skip extra error messages.
                self.msg.final_without_value(s)
        return True

    def check_final_implicit_def(self, s: AssignmentStmt) -> None:
        """Do basic checks for final declaration on self in __init__.

        Additional re-definition checks are performed by `analyze_lvalue`.
        """
        if not s.is_final_def:
            return
        lval = s.lvalues[0]
        assert isinstance(lval, RefExpr)
        if isinstance(lval, MemberExpr):
            if not self.is_self_member_ref(lval):
                self.fail("Final can be only applied to a name or an attribute on self", s)
                s.is_final_def = False
                return
            else:
                assert self.function_stack
                if self.function_stack[-1].name() != '__init__':
                    self.fail("Can only declare a final attribute in class body or __init__", s)
                    s.is_final_def = False
                    return

    def store_final_status(self, s: AssignmentStmt) -> None:
        """If this is a locally valid final declaration, set the corresponding flag on `Var`."""
        if s.is_final_def:
            if len(s.lvalues) == 1 and isinstance(s.lvalues[0], RefExpr):
                node = s.lvalues[0].node
                if isinstance(node, Var):
                    node.is_final = True
                    node.final_value = self.unbox_literal(s.rvalue)
                    if (self.is_class_scope() and
                            (isinstance(s.rvalue, TempNode) and s.rvalue.no_rhs)):
                        node.final_unset_in_class = True
        else:
            # Special case: deferred initialization of a final attribute in __init__.
            # In this case we just pretend this is a valid final definition to suppress
            # errors about assigning to final attribute.
            for lval in self.flatten_lvalues(s.lvalues):
                if isinstance(lval, MemberExpr) and self.is_self_member_ref(lval):
                    assert self.type, "Self member outside a class"
                    cur_node = self.type.names.get(lval.name, None)
                    if cur_node and isinstance(cur_node.node, Var) and cur_node.node.is_final:
                        assert self.function_stack
                        top_function = self.function_stack[-1]
                        if (top_function.name() == '__init__' and
                                cur_node.node.final_unset_in_class and
                                not cur_node.node.final_set_in_init and
                                not (isinstance(s.rvalue, TempNode) and s.rvalue.no_rhs)):
                            cur_node.node.final_set_in_init = True
                            s.is_final_def = True

    def flatten_lvalues(self, lvalues: List[Expression]) -> List[Expression]:
        res = []  # type: List[Expression]
        for lv in lvalues:
            if isinstance(lv, (TupleExpr, ListExpr)):
                res.extend(self.flatten_lvalues(lv.items))
            else:
                res.append(lv)
        return res

    def unbox_literal(self, e: Expression) -> Optional[Union[int, float, bool, str]]:
        if isinstance(e, (IntExpr, FloatExpr, StrExpr)):
            return e.value
        elif isinstance(e, NameExpr) and e.name in ('True', 'False'):
            return True if e.name == 'True' else False
        return None

    def process_type_annotation(self, s: AssignmentStmt) -> None:
        """Analyze type annotation or infer simple literal type."""
        if s.type:
            lvalue = s.lvalues[-1]
            allow_tuple_literal = isinstance(lvalue, TupleExpr)
            s.type = self.anal_type(s.type, allow_tuple_literal=allow_tuple_literal)
            if (self.type and self.type.is_protocol and isinstance(lvalue, NameExpr) and
                    isinstance(s.rvalue, TempNode) and s.rvalue.no_rhs):
                if isinstance(lvalue.node, Var):
                    lvalue.node.is_abstract_var = True
        else:
            if (any(isinstance(lv, NameExpr) and lv.is_inferred_def for lv in s.lvalues) and
                    self.type and self.type.is_protocol and not self.is_func_scope()):
                self.fail('All protocol members must have explicitly declared types', s)
            # Set the type if the rvalue is a simple literal (even if the above error occurred).
            if len(s.lvalues) == 1 and isinstance(s.lvalues[0], RefExpr):
                if s.lvalues[0].is_inferred_def:
                    s.type = self.analyze_simple_literal_type(s.rvalue, s.is_final_def)
        if s.type:
            # Store type into nodes.
            for lvalue in s.lvalues:
                self.store_declared_types(lvalue, s.type)

    def analyze_simple_literal_type(self, rvalue: Expression, is_final: bool) -> Optional[Type]:
        """Return builtins.int if rvalue is an int literal, etc.

        If this is a 'Final' context, we return "Literal[...]" instead."""
        if self.options.semantic_analysis_only or self.function_stack:
            # Skip this if we're only doing the semantic analysis pass.
            # This is mostly to avoid breaking unit tests.
            # Also skip inside a function; this is to avoid confusing
            # the code that handles dead code due to isinstance()
            # inside type variables with value restrictions (like
            # AnyStr).
            return None
        if isinstance(rvalue, FloatExpr):
            return self.named_type_or_none('builtins.float')

        value = None  # type: Optional[LiteralValue]
        type_name = None  # type: Optional[str]
        if isinstance(rvalue, IntExpr):
            value, type_name = rvalue.value, 'builtins.int'
        if isinstance(rvalue, StrExpr):
            value, type_name = rvalue.value, 'builtins.str'
        if isinstance(rvalue, BytesExpr):
            value, type_name = rvalue.value, 'builtins.bytes'
        if isinstance(rvalue, UnicodeExpr):
            value, type_name = rvalue.value, 'builtins.unicode'

        if type_name is not None:
            assert value is not None
            typ = self.named_type_or_none(type_name)
            if typ and is_final:
                return typ.copy_modified(final_value=LiteralType(
                    value=value,
                    fallback=typ,
                    line=typ.line,
                    column=typ.column,
                ))
            return typ

        return None

    def analyze_alias(self, rvalue: Expression) -> Tuple[Optional[Type], List[str],
                                                         Set[str], List[str]]:
        """Check if 'rvalue' is a valid type allowed for aliasing (e.g. not a type variable).

        If yes, return the corresponding type, a list of
        qualified type variable names for generic aliases, a set of names the alias depends on,
        and a list of type variables if the alias is generic.
        An schematic example for the dependencies:
            A = int
            B = str
            analyze_alias(Dict[A, B])[2] == {'__main__.A', '__main__.B'}
        """
        dynamic = bool(self.function_stack and self.function_stack[-1].is_dynamic())
        global_scope = not self.type and not self.function_stack
        res = analyze_type_alias(rvalue,
                                 self,
                                 self.tvar_scope,
                                 self.plugin,
                                 self.options,
                                 self.is_typeshed_stub_file,
                                 allow_unnormalized=self.is_stub_file,
                                 in_dynamic_func=dynamic,
                                 global_scope=global_scope)
        typ = None  # type: Optional[Type]
        if res:
            typ, depends_on = res
            found_type_vars = typ.accept(TypeVariableQuery(self.lookup_qualified, self.tvar_scope))
            alias_tvars = [name for (name, node) in found_type_vars]
            qualified_tvars = [node.fullname() for (name, node) in found_type_vars]
        else:
            alias_tvars = []
            depends_on = set()
            qualified_tvars = []
        return typ, alias_tvars, depends_on, qualified_tvars

    def check_and_set_up_type_alias(self, s: AssignmentStmt) -> None:
        """Check if assignment creates a type alias and set it up as needed.

        For simple aliases like L = List we use a simpler mechanism, just copying TypeInfo.
        For subscripted (including generic) aliases the resulting types are stored
        in rvalue.analyzed.
        """
        lvalue = s.lvalues[0]
        if len(s.lvalues) > 1 or not isinstance(lvalue, NameExpr):
            # First rule: Only simple assignments like Alias = ... create aliases.
            return
        if s.type:
            # Second rule: Explicit type (cls: Type[A] = A) always creates variable, not alias.
            return
        non_global_scope = self.type or self.is_func_scope()
        if isinstance(s.rvalue, RefExpr) and non_global_scope and lvalue.is_inferred_def:
            # Third rule: Non-subscripted right hand side creates a variable
            # at class and function scopes. For example:
            #
            #   class Model:
            #       ...
            #   class C:
            #       model = Model # this is automatically a variable with type 'Type[Model]'
            #
            # without this rule, this typical use case will require a lot of explicit
            # annotations (see the second rule).
            return
        rvalue = s.rvalue
        res, alias_tvars, depends_on, qualified_tvars = self.analyze_alias(rvalue)
        if not res:
            return
        if (isinstance(res, Instance) and res.type.name() == lvalue.name and
                res.type.module_name == self.cur_mod_id):
            # Aliases like C = C is a no-op.
            return
        s.is_alias_def = True
        node = self.lookup(lvalue.name, lvalue)
        assert node is not None
        assert node.node is not None
        self.add_type_alias_deps(depends_on)
        # In addition to the aliases used, we add deps on unbound
        # type variables, since they are erased from target type.
        self.add_type_alias_deps(qualified_tvars)
        # The above are only direct deps on other aliases.
        # For subscripted aliases, type deps from expansion are added in deps.py
        # (because the type is stored)
        if not lvalue.is_inferred_def:
            # Type aliases can't be re-defined.
            if isinstance(node.node, (TypeAlias, TypeInfo)):
                self.fail('Cannot assign multiple types to name "{}"'
                          ' without an explicit "Type[...]" annotation'
                          .format(lvalue.name), lvalue)
            return
        check_for_explicit_any(res, self.options, self.is_typeshed_stub_file, self.msg,
                               context=s)
        # when this type alias gets "inlined", the Any is not explicit anymore,
        # so we need to replace it with non-explicit Anys
        res = make_any_non_explicit(res)
        no_args = isinstance(res, Instance) and not res.args
        if isinstance(s.rvalue, (IndexExpr, CallExpr)):  # CallExpr is for `void = type(None)`
            s.rvalue.analyzed = TypeAliasExpr(res, alias_tvars, no_args)
            s.rvalue.analyzed.line = s.line
            # we use the column from resulting target, to get better location for errors
            s.rvalue.analyzed.column = res.column
        elif isinstance(s.rvalue, RefExpr):
            s.rvalue.is_alias_rvalue = True
        node.node = TypeAlias(res, node.node.fullname(), s.line, s.column,
                              alias_tvars=alias_tvars, no_args=no_args)
        if isinstance(rvalue, RefExpr) and isinstance(rvalue.node, TypeAlias):
            node.node.normalized = rvalue.node.normalized

    def analyze_lvalue(self, lval: Lvalue, nested: bool = False,
                       add_global: bool = False,
                       explicit_type: bool = False,
                       is_final: bool = False) -> None:
        """Analyze an lvalue or assignment target.

        Note that this is used in both pass 1 and 2.

        Args:
            lval: The target lvalue
            nested: If true, the lvalue is within a tuple or list lvalue expression
            add_global: Add name to globals table only if this is true (used in first pass)
            explicit_type: Assignment has type annotation
        """
        if isinstance(lval, NameExpr):
            self.analyze_name_lvalue(lval, add_global, explicit_type, is_final)
        elif isinstance(lval, MemberExpr):
            if not add_global:
                self.analyze_member_lvalue(lval, explicit_type, is_final)
            if explicit_type and not self.is_self_member_ref(lval):
                self.fail('Type cannot be declared in assignment to non-self '
                          'attribute', lval)
        elif isinstance(lval, IndexExpr):
            if explicit_type:
                self.fail('Unexpected type declaration', lval)
            if not add_global:
                lval.accept(self)
        elif isinstance(lval, TupleExpr):
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

    def analyze_name_lvalue(self,
                            lval: NameExpr,
                            add_global: bool,
                            explicit_type: bool,
                            is_final: bool) -> None:
        """Analyze an lvalue that targets a name expression.

        Arguments are similar to "analyze_lvalue".
        """
        if self.is_alias_for_final_name(lval.name):
            if is_final:
                self.fail("Cannot redefine an existing name as final", lval)
            else:
                self.msg.cant_assign_to_final(lval.name, self.type is not None, lval)

        # Top-level definitions within some statements (at least while) are
        # not handled in the first pass, so they have to be added now.
        nested_global = (not self.is_func_scope() and
                         self.block_depth[-1] > 0 and
                         not self.type)
        if (add_global or nested_global) and lval.name not in self.globals:
            # Define new global name.
            v = self.make_name_lvalue_var(lval, GDEF, not explicit_type)
            self.globals[lval.name] = SymbolTableNode(GDEF, v)
        elif isinstance(lval.node, Var) and lval.is_new_def:
            if lval.kind == GDEF:
                # Since the is_new_def flag is set, this must have been analyzed
                # already in the first pass and added to the symbol table.
                # An exception is typing module with incomplete test fixtures.
                assert lval.node.name() in self.globals or self.cur_mod_id == 'typing'
                # A previously defined name cannot be redefined as a final name even when
                # using renaming.
                if (is_final
                        and self.is_mangled_global(lval.name)
                        and not self.is_initial_mangled_global(lval.name)):
                    self.fail("Cannot redefine an existing name as final", lval)
        elif (self.locals[-1] is not None and lval.name not in self.locals[-1] and
              lval.name not in self.global_decls[-1] and
              lval.name not in self.nonlocal_decls[-1]):
            # Define new local name.
            v = self.make_name_lvalue_var(lval, LDEF, not explicit_type)
            self.add_local(v, lval)
            if unmangle(lval.name) == '_':
                # Special case for assignment to local named '_': always infer 'Any'.
                typ = AnyType(TypeOfAny.special_form)
                self.store_declared_types(lval, typ)
        elif not self.is_func_scope() and (self.type and
                                           lval.name not in self.type.names):
            # Define a new attribute within class body.
            if is_final and unmangle(lval.name) + "'" in self.type.names:
                self.fail("Cannot redefine an existing name as final", lval)
            v = self.make_name_lvalue_var(lval, MDEF, not explicit_type)
            self.type.names[lval.name] = SymbolTableNode(MDEF, v)
        else:
            self.make_name_lvalue_point_to_existing_def(lval, explicit_type, is_final)

    def is_mangled_global(self, name: str) -> bool:
        # A global is mangled if there exists at least one renamed variant.
        return unmangle(name) + "'" in self.globals

    def is_initial_mangled_global(self, name: str) -> bool:
        # If there are renamed definitions for a global, the first one has exactly one prime.
        return name == unmangle(name) + "'"

    def is_alias_for_final_name(self, name: str) -> bool:
        if self.is_func_scope():
            if not name.endswith("'"):
                # Not a mangled name -- can't be an alias
                return False
            name = unmangle(name)
            assert self.locals[-1] is not None, "No locals at function scope"
            existing = self.locals[-1].get(name)
            return existing is not None and is_final_node(existing.node)
        elif self.type is not None:
            orig_name = unmangle(name) + "'"
            if name == orig_name:
                return False
            existing = self.type.names.get(orig_name)
            return existing is not None and is_final_node(existing.node)
        else:
            orig_name = unmangle(name) + "'"
            if name == orig_name:
                return False
            existing = self.globals.get(orig_name)
            return existing is not None and is_final_node(existing.node)

    def make_name_lvalue_var(self, lvalue: NameExpr, kind: int, inferred: bool) -> Var:
        """Return a Var node for an lvalue that is a name expression."""
        v = Var(lvalue.name)
        v.set_line(lvalue)
        v.is_inferred = inferred
        if kind == MDEF:
            assert self.type is not None
            v.info = self.type
            v.is_initialized_in_class = True
        if kind != LDEF:
            v._fullname = self.qualified_name(lvalue.name)
        if kind == GDEF:
            v.is_ready = False  # Type not inferred yet
        lvalue.node = v
        lvalue.is_new_def = True
        lvalue.is_inferred_def = True
        lvalue.kind = kind
        if kind == GDEF:
            lvalue.fullname = v._fullname
        else:
            lvalue.fullname = lvalue.name
        return v

    def make_name_lvalue_point_to_existing_def(
            self,
            lval: NameExpr,
            explicit_type: bool,
            is_final: bool) -> None:
        """Update an lvalue to point to existing definition in the same scope.

        Arguments are similar to "analyze_lvalue".
        """
        # Assume that an existing name exists. Try to find the original definition.
        global_def = self.globals.get(lval.name)
        if self.locals:
            locals_last = self.locals[-1]
            if locals_last:
                local_def = locals_last.get(lval.name)
            else:
                local_def = None
        else:
            local_def = None
        type_def = self.type.names.get(lval.name) if self.type else None

        original_def = global_def or local_def or type_def

        # Redefining an existing name with final is always an error.
        if is_final:
            self.fail("Cannot redefine an existing name as final", lval)
        if explicit_type:
            # Don't re-bind types
            self.name_already_defined(lval.name, lval, original_def)
        else:
            # Bind to an existing name.
            lval.accept(self)
            self.check_lvalue_validity(lval.node, lval)

    def analyze_tuple_or_list_lvalue(self, lval: TupleExpr,
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
                                    explicit_type=explicit_type)

    def analyze_member_lvalue(self, lval: MemberExpr, explicit_type: bool, is_final: bool) -> None:
        """Analyze lvalue that is a member expression.

        Arguments:
            lval: The target lvalue
            explicit_type: Assignment has type annotation
            is_final: Is the target final
        """
        lval.accept(self)
        if self.is_self_member_ref(lval):
            assert self.type, "Self member outside a class"
            cur_node = self.type.names.get(lval.name, None)
            node = self.type.get(lval.name)
            if cur_node and is_final:
                # Overrides will be checked in type checker.
                self.fail("Cannot redefine an existing name as final", lval)
            # If the attribute of self is not defined in superclasses, create a new Var, ...
            if ((node is None or isinstance(node.node, Var) and node.node.is_abstract_var) or
                    # ... also an explicit declaration on self also creates a new Var.
                    # Note that `explicit_type` might has been erased for bare `Final`,
                    # so we also check if `final_cb` is passed.
                    (cur_node is None and (explicit_type or is_final))):
                if self.type.is_protocol and node is None:
                    self.fail("Protocol members cannot be defined via assignment to self", lval)
                else:
                    # Implicit attribute definition in __init__.
                    lval.is_new_def = True
                    lval.is_inferred_def = True
                    v = Var(lval.name)
                    v.set_line(lval)
                    v._fullname = self.qualified_name(lval.name)
                    v.info = self.type
                    v.is_ready = False
                    lval.def_var = v
                    lval.node = v
                    # TODO: should we also set lval.kind = MDEF?
                    self.type.names[lval.name] = SymbolTableNode(MDEF, v, implicit=True)
        self.check_lvalue_validity(lval.node, lval)

    def is_self_member_ref(self, memberexpr: MemberExpr) -> bool:
        """Does memberexpr to refer to an attribute of self?"""
        if not isinstance(memberexpr.expr, NameExpr):
            return False
        node = memberexpr.expr.node
        return isinstance(node, Var) and node.is_self

    def check_lvalue_validity(self, node: Union[Expression, SymbolNode, None],
                              ctx: Context) -> None:
        if isinstance(node, TypeVarExpr):
            self.fail('Invalid assignment target', ctx)
        elif isinstance(node, TypeInfo):
            self.fail(message_registry.CANNOT_ASSIGN_TO_TYPE, ctx)

    def store_declared_types(self, lvalue: Lvalue, typ: Type) -> None:
        if isinstance(typ, StarType) and not isinstance(lvalue, StarExpr):
            self.fail('Star type only allowed for starred expressions', lvalue)
        if isinstance(lvalue, RefExpr):
            lvalue.is_inferred_def = False
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

    def process_typevar_declaration(self, s: AssignmentStmt) -> None:
        """Check if s declares a TypeVar; it yes, store it in symbol table."""
        call = self.get_typevar_declaration(s)
        if not call:
            return

        lvalue = s.lvalues[0]
        assert isinstance(lvalue, NameExpr)
        name = lvalue.name
        if not lvalue.is_inferred_def:
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

        if self.options.disallow_any_unimported:
            for idx, constraint in enumerate(values, start=1):
                if has_any_from_unimported_type(constraint):
                    prefix = "Constraint {}".format(idx)
                    self.msg.unimported_type_becomes_any(prefix, constraint, s)

            if has_any_from_unimported_type(upper_bound):
                prefix = "Upper bound of type variable"
                self.msg.unimported_type_becomes_any(prefix, upper_bound, s)

        for t in values + [upper_bound]:
            check_for_explicit_any(t, self.options, self.is_typeshed_stub_file, self.msg,
                                   context=s)

        # mypyc suppresses making copies of a function to check each
        # possible type, so set the upper bound to Any to prevent that
        # from causing errors.
        if values and self.options.mypyc:
            upper_bound = AnyType(TypeOfAny.implementation_artifact)

        # Yes, it's a valid type variable definition! Add it to the symbol table.
        node = self.lookup(name, s)
        assert node is not None
        assert node.fullname is not None
        node.kind = self.current_symbol_kind()
        type_var = TypeVarExpr(name, node.fullname, values, upper_bound, variance)
        type_var.line = call.line
        call.analyzed = type_var
        node.node = type_var

    def check_typevar_name(self, call: CallExpr, name: str, context: Context) -> bool:
        name = unmangle(name)
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
                    # We want to use our custom error message below, so we suppress
                    # the default error message for invalid types here.
                    upper_bound = self.expr_to_analyzed_type(param_value,
                                                             report_invalid_types=False)
                    if isinstance(upper_bound, AnyType) and upper_bound.is_from_error:
                        self.fail("TypeVar 'bound' must be a type", param_value)
                        # Note: we do not return 'None' here -- we want to continue
                        # using the AnyType as the upper bound.
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

    def basic_new_typeinfo(self, name: str, basetype_or_fallback: Instance) -> TypeInfo:
        class_def = ClassDef(name, Block([]))
        class_def.fullname = self.qualified_name(name)

        info = TypeInfo(SymbolTable(), class_def, self.cur_mod_id)
        class_def.info = info
        mro = basetype_or_fallback.type.mro
        if not mro:
            # Forward reference, MRO should be recalculated in third pass.
            mro = [basetype_or_fallback.type, self.object_type().type]
        info.mro = [info] + mro
        info.bases = [basetype_or_fallback]
        return info

    def analyze_types(self, items: List[Expression]) -> List[Type]:
        result = []  # type: List[Type]
        for node in items:
            try:
                result.append(self.anal_type(expr_to_unanalyzed_type(node)))
            except TypeTranslationError:
                self.fail('Type expected', node)
                result.append(AnyType(TypeOfAny.from_error))
        return result

    def parse_bool(self, expr: Expression) -> Optional[bool]:
        if isinstance(expr, NameExpr):
            if expr.fullname == 'builtins.True':
                return True
            if expr.fullname == 'builtins.False':
                return False
        return None

    def check_classvar(self, s: AssignmentStmt) -> None:
        """Check if assignment defines a class variable."""
        lvalue = s.lvalues[0]
        if len(s.lvalues) != 1 or not isinstance(lvalue, RefExpr):
            return
        if not s.type or not self.is_classvar(s.type):
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

    def is_final_type(self, typ: Type) -> bool:
        if not isinstance(typ, UnboundType):
            return False
        sym = self.lookup_qualified(typ.name, typ)
        if not sym or not sym.node:
            return False
        return sym.node.fullname() in ('typing.Final',
                                       'typing_extensions.Final')

    def fail_invalid_classvar(self, context: Context) -> None:
        self.fail('ClassVar can only be used for assignments in class body', context)

    def process_module_assignment(self, lvals: List[Lvalue], rval: Expression,
                                  ctx: AssignmentStmt) -> None:
        """Propagate module references across assignments.

        Recursively handles the simple form of iterable unpacking; doesn't
        handle advanced unpacking with *rest, dictionary unpacking, etc.

        In an expression like x = y = z, z is the rval and lvals will be [x,
        y].

        """
        if (isinstance(rval, (TupleExpr, ListExpr))
                and all(isinstance(v, TupleExpr) for v in lvals)):
            # rval and all lvals are either list or tuple, so we are dealing
            # with unpacking assignment like `x, y = a, b`. Mypy didn't
            # understand our all(isinstance(...)), so cast them as TupleExpr
            # so mypy knows it is safe to access their .items attribute.
            seq_lvals = cast(List[TupleExpr], lvals)
            # given an assignment like:
            #     (x, y) = (m, n) = (a, b)
            # we now have:
            #     seq_lvals = [(x, y), (m, n)]
            #     seq_rval = (a, b)
            # We now zip this into:
            #     elementwise_assignments = [(a, x, m), (b, y, n)]
            # where each elementwise assignment includes one element of rval and the
            # corresponding element of each lval. Basically we unpack
            #     (x, y) = (m, n) = (a, b)
            # into elementwise assignments
            #     x = m = a
            #     y = n = b
            # and then we recursively call this method for each of those assignments.
            # If the rval and all lvals are not all of the same length, zip will just ignore
            # extra elements, so no error will be raised here; mypy will later complain
            # about the length mismatch in type-checking.
            elementwise_assignments = zip(rval.items, *[v.items for v in seq_lvals])
            # TODO: use 'for rv, *lvs in' once mypyc supports it
            for part in elementwise_assignments:
                rv, lvs = part[0], list(part[1:])
                self.process_module_assignment(lvs, rv, ctx)
        elif isinstance(rval, RefExpr):
            rnode = self.lookup_type_node(rval)
            if rnode and isinstance(rnode.node, MypyFile):
                for lval in lvals:
                    if not isinstance(lval, NameExpr):
                        continue
                    # respect explicitly annotated type
                    if (isinstance(lval.node, Var) and lval.node.type is not None):
                        continue
                    lnode = self.lookup(lval.name, ctx)
                    if lnode:
                        if isinstance(lnode.node, MypyFile) and lnode.node is not rnode.node:
                            self.fail(
                                "Cannot assign multiple modules to name '{}' "
                                "without explicit 'types.ModuleType' annotation".format(lval.name),
                                ctx)
                        # never create module alias except on initial var definition
                        elif lval.is_inferred_def:
                            lnode.kind = self.current_symbol_kind()
                            lnode.node = rnode.node

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
                dec.var.type = AnyType(TypeOfAny.special_form)
                no_type_check = True
            elif (refers_to_fullname(d, 'typing.final') or
                  refers_to_fullname(d, 'typing_extensions.final')):
                if self.is_class_scope():
                    assert self.type is not None, "No type set at class scope"
                    if self.type.is_protocol:
                        self.msg.protocol_members_cant_be_final(d)
                    else:
                        dec.func.is_final = True
                        dec.var.is_final = True
                    removed.append(i)
                else:
                    self.fail("@final cannot be used with non-method functions", d)
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
        if not no_type_check and self.recurse_into_functions:
            dec.func.accept(self)
        if dec.decorators and dec.var.is_property:
            self.fail('Decorated property not supported', dec)

    def check_decorated_function_is_method(self, decorator: str,
                                           context: Context) -> None:
        if not self.type or self.is_func_scope():
            self.fail("'%s' used with a non-method" % decorator, context)

    def process__all__(self, s: AssignmentStmt) -> None:
        """Export names if argument is a __all__ assignment."""
        if (len(s.lvalues) == 1 and isinstance(s.lvalues[0], NameExpr) and
                s.lvalues[0].name == '__all__' and s.lvalues[0].kind == GDEF and
                isinstance(s.rvalue, (ListExpr, TupleExpr))):
            self.add_exports(s.rvalue.items)

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
            self.add_exports(s.rvalue.items)

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
            allow_tuple_literal = isinstance(s.index, TupleExpr)
            s.index_type = self.anal_type(s.index_type, allow_tuple_literal=allow_tuple_literal)
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
        infer_reachability_of_if_statement(s, self.options)
        for i in range(len(s.expr)):
            s.expr[i].accept(self)
            self.visit_block(s.body[i])
        self.visit_block_maybe(s.else_body)

    def visit_try_stmt(self, s: TryStmt) -> None:
        self.analyze_try_stmt(s, self)

    def analyze_try_stmt(self, s: TryStmt, visitor: NodeVisitor[None],
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
                    allow_tuple_literal = isinstance(n, TupleExpr)
                    t = self.anal_type(t, allow_tuple_literal=allow_tuple_literal)
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
        if s.globals:
            s.globals.accept(self)
        if s.locals:
            s.locals.accept(self)

    #
    # Expressions
    #

    def visit_name_expr(self, expr: NameExpr) -> None:
        n = self.lookup(expr.name, expr)
        if n:
            if isinstance(n.node, TypeVarExpr) and self.tvar_scope.get_binding(n):
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
        for arg in expr.call.args:
            arg.accept(self)

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
        if expr.analyzed:
            return
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
            expr.analyzed = RevealExpr(kind=REVEAL_TYPE, expr=expr.args[0])
            expr.analyzed.line = expr.line
            expr.analyzed.column = expr.column
            expr.analyzed.accept(self)
        elif refers_to_fullname(expr.callee, 'builtins.reveal_locals'):
            # Store the local variable names into the RevealExpr for use in the
            # type checking pass
            local_nodes = []  # type: List[Var]
            if self.is_module_scope():
                # try to determine just the variable declarations in module scope
                # self.globals.values() contains SymbolTableNode's
                # Each SymbolTableNode has an attribute node that is nodes.Var
                # look for variable nodes that marked as is_inferred
                # Each symboltable node has a Var node as .node
                local_nodes = [n.node
                               for name, n in self.globals.items()
                               if getattr(n.node, 'is_inferred', False)
                               and isinstance(n.node, Var)]
            elif self.is_class_scope():
                # type = None  # type: Optional[TypeInfo]
                if self.type is not None:
                    local_nodes = [st.node
                                   for st in self.type.names.values()
                                   if isinstance(st.node, Var)]
            elif self.is_func_scope():
                # locals = None  # type: List[Optional[SymbolTable]]
                if self.locals is not None:
                    symbol_table = self.locals[-1]
                    if symbol_table is not None:
                        local_nodes = [st.node
                                       for st in symbol_table.values()
                                       if isinstance(st.node, Var)]
            expr.analyzed = RevealExpr(kind=REVEAL_LOCALS, local_nodes=local_nodes)
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
        elif refers_to_fullname(expr.callee, 'builtins.divmod'):
            if not self.check_fixed_args(expr, 2, 'divmod'):
                return
            expr.analyzed = OpExpr('divmod', expr.args[0], expr.args[1])
            expr.analyzed.line = expr.line
            expr.analyzed.accept(self)
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
                    self.add_exports(expr.args[0].items)

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
        expr = DictExpr([(StrExpr(cast(str, key)), value)  # since they are all ARG_NAMED
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
        if isinstance(base, RefExpr) and isinstance(base.node, MypyFile):
            # This branch handles the case foo.bar where foo is a module.
            # In this case base.node is the module's MypyFile and we look up
            # bar in its namespace.  This must be done for all types of bar.
            file = cast(Optional[MypyFile], base.node)  # can't use isinstance due to issue #2999
            # TODO: Should we actually use this? Not sure if this makes a difference.
            # if file.fullname() == self.cur_mod_id:
            #     names = self.globals
            # else:
            #     names = file.names
            n = file.names.get(expr.name, None) if file is not None else None
            n = self.dereference_module_cross_ref(n)
            if n and not n.module_hidden:
                if not n:
                    return
                n = self.rebind_symbol_table_node(n)
                if n:
                    # TODO: What if None?
                    expr.kind = n.kind
                    expr.fullname = n.fullname
                    expr.node = n.node
            elif (file is not None and (file.is_stub or self.options.python_version >= (3, 7))
                    and '__getattr__' in file.names):
                # If there is a module-level __getattr__, then any attribute on the module is valid
                # per PEP 484.
                getattr_defn = file.names['__getattr__']
                if not getattr_defn:
                    typ = AnyType(TypeOfAny.from_error)  # type: Type
                elif isinstance(getattr_defn.node, (FuncDef, Var)):
                    if isinstance(getattr_defn.node.type, CallableType):
                        typ = getattr_defn.node.type.ret_type
                    else:
                        typ = AnyType(TypeOfAny.from_error)
                else:
                    typ = AnyType(TypeOfAny.from_error)
                expr.kind = GDEF
                expr.fullname = '{}.{}'.format(file.fullname(), expr.name)
                expr.node = Var(expr.name, type=typ)
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
        elif isinstance(base, RefExpr):
            # This branch handles the case C.bar (or cls.bar or self.bar inside
            # a classmethod/method), where C is a class and bar is a type
            # definition or a module resulting from `import bar` (or a module
            # assignment) inside class C. We look up bar in the class' TypeInfo
            # namespace.  This is done only when bar is a module or a type;
            # other things (e.g. methods) are handled by other code in
            # checkmember.
            type_info = None
            if isinstance(base.node, TypeInfo):
                # C.bar where C is a class
                type_info = base.node
            elif isinstance(base.node, Var) and self.type and self.function_stack:
                # check for self.bar or cls.bar in method/classmethod
                func_def = self.function_stack[-1]
                if not func_def.is_static and isinstance(func_def.type, CallableType):
                    formal_arg = func_def.type.argument_by_name(base.node.name())
                    if formal_arg and formal_arg.pos == 0:
                        type_info = self.type
            elif isinstance(base.node, TypeAlias) and base.node.no_args:
                if isinstance(base.node.target, Instance):
                    type_info = base.node.target.type

            if type_info:
                n = type_info.names.get(expr.name)
                if n is not None and isinstance(n.node, (MypyFile, TypeInfo, TypeAlias)):
                    if not n:
                        return
                    expr.kind = n.kind
                    expr.fullname = n.fullname
                    expr.node = n.node

    def visit_op_expr(self, expr: OpExpr) -> None:
        expr.left.accept(self)

        if expr.op in ('and', 'or'):
            inferred = infer_condition_value(expr.left, self.options)
            if ((inferred in (ALWAYS_FALSE, MYPY_FALSE) and expr.op == 'and') or
                    (inferred in (ALWAYS_TRUE, MYPY_TRUE) and expr.op == 'or')):
                expr.right_unreachable = True
                return
            elif ((inferred in (ALWAYS_TRUE, MYPY_TRUE) and expr.op == 'and') or
                    (inferred in (ALWAYS_FALSE, MYPY_FALSE) and expr.op == 'or')):
                expr.right_always = True

        expr.right.accept(self)

    def visit_comparison_expr(self, expr: ComparisonExpr) -> None:
        for operand in expr.operands:
            operand.accept(self)

    def visit_unary_expr(self, expr: UnaryExpr) -> None:
        expr.expr.accept(self)

    def visit_index_expr(self, expr: IndexExpr) -> None:
        if expr.analyzed:
            return
        expr.base.accept(self)
        if (isinstance(expr.base, RefExpr)
                and isinstance(expr.base.node, TypeInfo)
                and not expr.base.node.is_generic()):
            expr.index.accept(self)
        elif (isinstance(expr.base, RefExpr) and isinstance(expr.base.node, TypeAlias) or
                refers_to_class_or_function(expr.base)):
            # Special form -- type application (either direct or via type aliasing).

            self.analyze_type_expr(expr.index)

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
                # We always allow unbound type variables in IndexExpr, since we
                # may be analysing a type alias definition rvalue. The error will be
                # reported elsewhere if it is not the case.
                typearg = self.anal_type(typearg, allow_unbound_tvars=True)
                types.append(typearg)
            expr.analyzed = TypeApplication(expr.base, types)
            expr.analyzed.line = expr.line
            # Types list, dict, set are not subscriptable, prohibit this if
            # subscripted either via type alias...
            if isinstance(expr.base, RefExpr) and isinstance(expr.base.node, TypeAlias):
                alias = expr.base.node
                if isinstance(alias.target, Instance):
                    name = alias.target.type.fullname()
                    if (alias.no_args and  # this avoids bogus errors for already reported aliases
                            name in nongen_builtins and not alias.normalized):
                        self.fail(no_subscript_builtin_alias(name, propose_alt=False), expr)
            # ...or directly.
            else:
                n = self.lookup_type_node(expr.base)
                if n and n.fullname in nongen_builtins:
                    self.fail(no_subscript_builtin_alias(n.fullname, propose_alt=False), expr)
        else:
            expr.index.accept(self)

    def lookup_type_node(self, expr: Expression) -> Optional[SymbolTableNode]:
        try:
            t = expr_to_unanalyzed_type(expr)
        except TypeTranslationError:
            return None
        if isinstance(t, UnboundType):
            n = self.lookup_qualified(t.name, expr, suppress_errors=True)
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

    def visit_reveal_expr(self, expr: RevealExpr) -> None:
        if expr.kind == REVEAL_TYPE:
            if expr.expr is not None:
                expr.expr.accept(self)
        else:
            # Reveal locals doesn't have an inner expression, there's no
            # need to traverse inside it
            pass

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

    @contextmanager
    def tvar_scope_frame(self, frame: TypeVarScope) -> Iterator[None]:
        old_scope = self.tvar_scope
        self.tvar_scope = frame
        yield
        self.tvar_scope = old_scope

    def lookup(self, name: str, ctx: Context,
               suppress_errors: bool = False) -> Optional[SymbolTableNode]:
        """Look up an unqualified name in all active namespaces."""
        implicit_name = False
        # 1a. Name declared using 'global x' takes precedence
        if name in self.global_decls[-1]:
            if name in self.globals:
                return self.globals[name]
            if not suppress_errors:
                self.name_not_defined(name, ctx)
            return None
        # 1b. Name declared using 'nonlocal x' takes precedence
        if name in self.nonlocal_decls[-1]:
            for table in reversed(self.locals[:-1]):
                if table is not None and name in table:
                    return table[name]
            else:
                if not suppress_errors:
                    self.name_not_defined(name, ctx)
                return None
        # 2. Class attributes (if within class definition)
        if self.type and not self.is_func_scope() and name in self.type.names:
            node = self.type.names[name]
            if not node.implicit:
                return node
            implicit_name = True
            implicit_node = node
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
                    if not suppress_errors:
                        self.name_not_defined(name, ctx)
                    return None
                node = table[name]
                return node
        # Give up.
        if not implicit_name and not suppress_errors:
            self.name_not_defined(name, ctx)
            self.check_for_obsolete_short_name(name, ctx)
        else:
            if implicit_name:
                return implicit_node
        return None

    def check_for_obsolete_short_name(self, name: str, ctx: Context) -> None:
        matches = [obsolete_name
                   for obsolete_name in obsolete_name_mapping
                   if obsolete_name.rsplit('.', 1)[-1] == name]
        if len(matches) == 1:
            self.note("(Did you mean '{}'?)".format(obsolete_name_mapping[matches[0]]), ctx)

    def lookup_qualified(self, name: str, ctx: Context,
                         suppress_errors: bool = False) -> Optional[SymbolTableNode]:
        if '.' not in name:
            return self.lookup(name, ctx, suppress_errors=suppress_errors)
        else:
            parts = name.split('.')
            n = self.lookup(parts[0], ctx, suppress_errors=suppress_errors)
            if n:
                for i in range(1, len(parts)):
                    if isinstance(n.node, TypeInfo):
                        if not n.node.mro:
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
                        names = n.node.names
                        # Rebind potential references to old version of current module in
                        # fine-grained incremental mode.
                        #
                        # TODO: Do this for all modules in the set of modified files.
                        if n.node.fullname() == self.cur_mod_id:
                            names = self.globals
                        n = names.get(parts[i], None)
                        if n and isinstance(n.node, ImportedName):
                            n = self.dereference_module_cross_ref(n)
                        elif not n and '__getattr__' in names:
                            gvar = self.create_getattr_var(names['__getattr__'],
                                                           parts[i], parts[i])
                            if gvar:
                                names[name] = gvar
                                n = gvar
                    # TODO: What if node is Var or FuncDef?
                    # Currently, missing these cases results in controversial behavior, when
                    # lookup_qualified(x.y.z) returns Var(x).
                    if not n:
                        if not suppress_errors:
                            self.name_not_defined(name, ctx)
                        break
                if n:
                    if n and n.module_hidden:
                        self.name_not_defined(name, ctx)
            if n and not n.module_hidden:
                n = self.rebind_symbol_table_node(n)
                return n
            return None

    def create_getattr_var(self, getattr_defn: SymbolTableNode,
                           name: str, fullname: str) -> Optional[SymbolTableNode]:
        """Create a dummy global symbol using __getattr__ return type.

        If not possible, return None.
        """
        if isinstance(getattr_defn.node, (FuncDef, Var)):
            if isinstance(getattr_defn.node.type, CallableType):
                typ = getattr_defn.node.type.ret_type
            else:
                typ = AnyType(TypeOfAny.from_error)
            v = Var(name, type=typ)
            v._fullname = fullname
            return SymbolTableNode(GDEF, v)
        return None

    def rebind_symbol_table_node(self, n: SymbolTableNode) -> Optional[SymbolTableNode]:
        """If node refers to old version of module, return reference to new version.

        If the reference is removed in the new version, return None.
        """
        # TODO: Handle type variables and other sorts of references
        if isinstance(n.node, (FuncDef, OverloadedFuncDef, TypeInfo, Var, TypeAlias)):
            # TODO: Why is it possible for fullname() to be None, even though it's not
            #   annotated as Optional[str]?
            # TODO: Do this for all modules in the set of modified files
            # TODO: This doesn't work for things nested within classes
            if n.node.fullname() and get_prefix(n.node.fullname()) == self.cur_mod_id:
                # This is an indirect reference to a name defined in the current module.
                # Rebind it.
                return self.globals.get(n.node.name())
        # No need to rebind.
        return n

    def builtin_type(self, fully_qualified_name: str) -> Instance:
        sym = self.lookup_fully_qualified(fully_qualified_name)
        node = sym.node
        assert isinstance(node, TypeInfo)
        return Instance(node, [AnyType(TypeOfAny.special_form)] * len(node.defn.type_vars))

    def add_builtin_aliases(self, tree: MypyFile) -> None:
        """Add builtin type aliases to typing module.

        For historical reasons, the aliases like `List = list` are not defined
        in typeshed stubs for typing module. Instead we need to manually add the
        corresponding nodes on the fly. We explicitly mark these aliases as normalized,
        so that a user can write `typing.List[int]`.
        """
        assert tree.fullname() == 'typing'
        for alias, target_name in type_aliases.items():
            name = alias.split('.')[-1]
            n = self.lookup_fully_qualified_or_none(target_name)
            if n:
                target = self.named_type_or_none(target_name, [])
                assert target is not None
                alias_node = TypeAlias(target, alias, line=-1, column=-1,  # there is no context
                                       no_args=True, normalized=True)
                tree.names[name] = SymbolTableNode(GDEF, alias_node)
            else:
                # Built-in target not defined, remove the original fake
                # definition to trigger a better error message.
                tree.names.pop(name, None)

    def lookup_fully_qualified(self, name: str) -> SymbolTableNode:
        """Lookup a fully qualified name.

        Assume that the name is defined. This happens in the global namespace -- the local
        module namespace is ignored.
        """
        parts = name.split('.')
        n = self.modules[parts[0]]
        for i in range(1, len(parts) - 1):
            next_sym = n.names[parts[i]]
            assert isinstance(next_sym.node, MypyFile)
            n = next_sym.node
        return n.names[parts[-1]]

    def lookup_fully_qualified_or_none(self, fullname: str) -> Optional[SymbolTableNode]:
        """Lookup a fully qualified name that refers to a module-level definition.

        Don't assume that the name is defined. This happens in the global namespace --
        the local module namespace is ignored. This does not dereference indirect
        refs.

        Note that this can't be used for names nested in class namespaces.
        """
        # TODO: unify/clean-up/simplify lookup methods, see #4157.
        # TODO: support nested classes (but consider performance impact,
        #       we might keep the module level only lookup for thing like 'builtins.int').
        assert '.' in fullname
        module, name = fullname.rsplit('.', maxsplit=1)
        if module not in self.modules:
            return None
        filenode = self.modules[module]
        return filenode.names.get(name)

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

    def is_nested_within_func_scope(self) -> bool:
        """Are we underneath a function scope, even if we are in a nested class also"""
        return any(l is not None for l in self.locals)

    def is_class_scope(self) -> bool:
        return self.type is not None and not self.is_func_scope()

    def is_module_scope(self) -> bool:
        return not (self.is_class_scope() or self.is_func_scope())

    def current_symbol_kind(self) -> int:
        if self.is_class_scope():
            kind = MDEF
        elif self.is_func_scope():
            kind = LDEF
        else:
            kind = GDEF
        return kind

    def add_symbol(self, name: str, node: SymbolTableNode,
                   context: Context) -> None:
        """Add symbol to the currently active symbol table."""
        # NOTE: This logic mostly parallels SemanticAnalyzerPass1.add_symbol. If you change
        #     this, you may have to change the other method as well.
        # TODO: Combine these methods in the first and second pass into a single one.
        if self.is_func_scope():
            assert self.locals[-1] is not None
            if name in self.locals[-1]:
                # Flag redefinition unless this is a reimport of a module.
                if not (isinstance(node.node, MypyFile) and
                        self.locals[-1][name].node == node.node):
                    self.name_already_defined(name, context, self.locals[-1][name])
                    return
            self.locals[-1][name] = node
        elif self.type:
            existing = self.type.names.get(name)
            if existing and isinstance(existing.node, TypeInfo) and existing.node != node.node:
                self.name_already_defined(name, context, existing)
                return
            self.type.names[name] = node
        else:
            existing = self.globals.get(name)
            if (existing
                    and (not isinstance(node.node, MypyFile) or existing.node != node.node)
                    and existing.kind != UNBOUND_IMPORTED
                    and not isinstance(existing.node, ImportedName)):
                # Modules can be imported multiple times to support import
                # of multiple submodules of a package (e.g. a.x and a.y).
                ok = False
                # Only report an error if the symbol collision provides a different type.
                if existing.type and node.type and is_same_type(existing.type, node.type):
                    ok = True
                if not ok:
                    self.name_already_defined(name, context, existing)
                    return
            self.globals[name] = node

    def add_local(self, node: Union[Var, FuncDef, OverloadedFuncDef], ctx: Context) -> None:
        """Add local variable or function."""
        assert self.locals[-1] is not None, "Should not add locals outside a function"
        name = node.name()
        if name in self.locals[-1]:
            self.name_already_defined(name, ctx, self.locals[-1][name])
            return
        node._fullname = name
        self.locals[-1][name] = SymbolTableNode(LDEF, node)

    def add_exports(self, exp_or_exps: Union[Iterable[Expression], Expression]) -> None:
        exps = [exp_or_exps] if isinstance(exp_or_exps, Expression) else exp_or_exps
        for exp in exps:
            if isinstance(exp, StrExpr):
                self.all_exports.append(exp.value)

    def check_no_global(self, n: str, ctx: Context,
                        is_overloaded_func: bool = False) -> None:
        if n in self.globals:
            prev_is_overloaded = isinstance(self.globals[n], OverloadedFuncDef)
            if is_overloaded_func and prev_is_overloaded:
                self.fail("Nonconsecutive overload {} found".format(n), ctx)
            elif prev_is_overloaded:
                self.fail("Definition of '{}' missing 'overload'".format(n), ctx)
            else:
                self.name_already_defined(n, ctx, self.globals[n])

    def name_not_defined(self, name: str, ctx: Context) -> None:
        message = "Name '{}' is not defined".format(name)
        extra = self.undefined_name_extra_info(name)
        if extra:
            message += ' {}'.format(extra)
        self.fail(message, ctx)
        if 'builtins.{}'.format(name) in SUGGESTED_TEST_FIXTURES:
            # The user probably has a missing definition in a test fixture. Let's verify.
            fullname = 'builtins.{}'.format(name)
            if self.lookup_fully_qualified_or_none(fullname) is None:
                # Yes. Generate a helpful note.
                self.add_fixture_note(fullname, ctx)

    def name_already_defined(self, name: str, ctx: Context,
                    original_ctx: Optional[Union[SymbolTableNode, SymbolNode]] = None) -> None:
        if isinstance(original_ctx, SymbolTableNode):
            node = original_ctx.node
        elif isinstance(original_ctx, SymbolNode):
            node = original_ctx

        if isinstance(original_ctx, SymbolTableNode) and isinstance(original_ctx.node, MypyFile):
            # Since this is an import, original_ctx.node points to the module definition.
            # Therefore its line number is always 1, which is not useful for this
            # error message.
            extra_msg = ' (by an import)'
        elif node and node.line != -1:
            extra_msg = ' on line {}'.format(node.line)
        else:
            extra_msg = ' (possibly by an import)'
        self.fail("Name '{}' already defined{}".format(unmangle(name), extra_msg), ctx)

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

    def analyze_type_expr(self, expr: Expression) -> None:
        # There are certain expressions that mypy does not need to semantically analyze,
        # since they analyzed solely as type. (For example, indexes in type alias definitions
        # and base classes in class defs). External consumers of the mypy AST may need
        # them semantically analyzed, however, if they need to treat it as an expression
        # and not a type. (Which is to say, mypyc needs to do this.) Do the analysis
        # in a fresh tvar scope in order to suppress any errors about using type variables.
        with self.tvar_scope_frame(TypeVarScope()):
            expr.accept(self)

    def lookup_current_scope(self, name: str) -> Optional[SymbolTableNode]:
        if self.locals[-1] is not None:
            return self.locals[-1].get(name)
        elif self.type is not None:
            return self.type.names.get(name)
        else:
            return self.globals.get(name)

    def schedule_patch(self, priority: int, patch: Callable[[], None]) -> None:
        self.patches.append((priority, patch))

    def add_symbol_table_node(self, name: str, stnode: SymbolTableNode) -> None:
        """Add node to global symbol table (or to nearest class if there is one)."""
        # TODO: Adding to the nearest class is ad hoc.
        if self.type:
            self.type.names[name] = stnode
        else:
            self.globals[name] = stnode


def replace_implicit_first_type(sig: FunctionLike, new: Type) -> FunctionLike:
    if isinstance(sig, CallableType):
        if len(sig.arg_types) == 0:
            return sig
        return sig.copy_modified(arg_types=[new] + sig.arg_types[1:])
    elif isinstance(sig, Overloaded):
        return Overloaded([cast(CallableType, replace_implicit_first_type(i, new))
                           for i in sig.items()])
    else:
        assert False


def refers_to_fullname(node: Expression, fullname: str) -> bool:
    """Is node a name or member expression with the given full name?"""
    if not isinstance(node, RefExpr):
        return False
    return (node.fullname == fullname or
            isinstance(node.node, TypeAlias) and isinstance(node.node.target, Instance)
            and node.node.target.type.fullname() == fullname)


def refers_to_class_or_function(node: Expression) -> bool:
    """Does semantically analyzed node refer to a class?"""
    return (isinstance(node, RefExpr) and
            isinstance(node.node, (TypeInfo, FuncDef, OverloadedFuncDef)))


def find_duplicate(list: List[T]) -> Optional[T]:
    """If the list has duplicates, return one of the duplicates.

    Otherwise, return None.
    """
    for i in range(1, len(list)):
        if list[i] in list[:i]:
            return list[i]
    return None


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


def make_any_non_explicit(t: Type) -> Type:
    """Replace all Any types within in with Any that has attribute 'explicit' set to False"""
    return t.accept(MakeAnyNonExplicit())


class MakeAnyNonExplicit(TypeTranslator):
    def visit_any(self, t: AnyType) -> Type:
        if t.type_of_any == TypeOfAny.explicit:
            return t.copy_modified(TypeOfAny.special_form)
        return t


def apply_semantic_analyzer_patches(patches: List[Tuple[int, Callable[[], None]]]) -> None:
    """Call patch callbacks in the right order.

    This should happen after semantic analyzer pass 3.
    """
    patches_by_priority = sorted(patches, key=lambda x: x[0])
    for priority, patch_func in patches_by_priority:
        patch_func()
