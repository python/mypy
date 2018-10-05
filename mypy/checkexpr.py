"""Expression type checker. This file is conceptually part of TypeChecker."""

from collections import OrderedDict
from contextlib import contextmanager
from typing import (
    cast, Dict, Set, List, Tuple, Callable, Union, Optional, Iterable,
    Sequence, Iterator
)
MYPY = False
if MYPY:
    from typing import ClassVar
    from typing_extensions import Final

from mypy.errors import report_internal_error
from mypy.typeanal import (
    has_any_from_unimported_type, check_for_explicit_any, set_any_tvars, expand_type_alias
)
from mypy.types import (
    Type, AnyType, CallableType, Overloaded, NoneTyp, TypeVarDef,
    TupleType, TypedDictType, Instance, TypeVarType, ErasedType, UnionType,
    PartialType, DeletedType, UninhabitedType, TypeType, TypeOfAny,
    true_only, false_only, is_named_instance, function_type, callable_type, FunctionLike,
    StarType, is_optional, remove_optional, is_invariant_instance
)
from mypy.nodes import (
    NameExpr, RefExpr, Var, FuncDef, OverloadedFuncDef, TypeInfo, CallExpr,
    MemberExpr, IntExpr, StrExpr, BytesExpr, UnicodeExpr, FloatExpr,
    OpExpr, UnaryExpr, IndexExpr, CastExpr, RevealExpr, TypeApplication, ListExpr,
    TupleExpr, DictExpr, LambdaExpr, SuperExpr, SliceExpr, Context, Expression,
    ListComprehension, GeneratorExpr, SetExpr, MypyFile, Decorator,
    ConditionalExpr, ComparisonExpr, TempNode, SetComprehension,
    DictionaryComprehension, ComplexExpr, EllipsisExpr, StarExpr, AwaitExpr, YieldExpr,
    YieldFromExpr, TypedDictExpr, PromoteExpr, NewTypeExpr, NamedTupleExpr, TypeVarExpr,
    TypeAliasExpr, BackquoteExpr, EnumCallExpr, TypeAlias, SymbolNode,
    ARG_POS, ARG_OPT, ARG_NAMED, ARG_STAR, ARG_STAR2, MODULE_REF, LITERAL_TYPE, REVEAL_TYPE
)
from mypy.literals import literal
from mypy import nodes
import mypy.checker
from mypy import types
from mypy.sametypes import is_same_type
from mypy.erasetype import replace_meta_vars, erase_type
from mypy.messages import MessageBuilder
from mypy import messages
from mypy.infer import infer_type_arguments, infer_function_type_arguments
from mypy import join
from mypy.meet import narrow_declared_type
from mypy.subtypes import (
    is_subtype, is_proper_subtype, is_equivalent, find_member, non_method_protocol_members,
)
from mypy import applytype
from mypy import erasetype
from mypy.checkmember import analyze_member_access, type_object_type
from mypy.constraints import get_actual_type
from mypy.checkstrformat import StringFormatterChecker
from mypy.expandtype import expand_type, expand_type_by_instance, freshen_function_type_vars
from mypy.util import split_module_names
from mypy.typevars import fill_typevars
from mypy.visitor import ExpressionVisitor
from mypy.plugin import Plugin, MethodContext, MethodSigContext, FunctionContext
from mypy.typeanal import make_optional_type

# Type of callback user for checking individual function arguments. See
# check_args() below for details.
ArgChecker = Callable[[Type, Type, int, Type, int, int, CallableType, Context, MessageBuilder],
                      None]

# Maximum nesting level for math union in overloads, setting this to large values
# may cause performance issues. The reason is that although union math algorithm we use
# nicely captures most corner cases, its worst case complexity is exponential,
# see https://github.com/python/mypy/pull/5255#discussion_r196896335 for discussion.
MAX_UNIONS = 5  # type: Final


class TooManyUnions(Exception):
    """Indicates that we need to stop splitting unions in an attempt
    to match an overload in order to save performance.
    """


def extract_refexpr_names(expr: RefExpr) -> Set[str]:
    """Recursively extracts all module references from a reference expression.

    Note that currently, the only two subclasses of RefExpr are NameExpr and
    MemberExpr."""
    output = set()  # type: Set[str]
    while expr.kind == MODULE_REF or expr.fullname is not None:
        if expr.kind == MODULE_REF and expr.fullname is not None:
            # If it's None, something's wrong (perhaps due to an
            # import cycle or a suppressed error).  For now we just
            # skip it.
            output.add(expr.fullname)

        if isinstance(expr, NameExpr):
            is_suppressed_import = isinstance(expr.node, Var) and expr.node.is_suppressed_import
            if isinstance(expr.node, TypeInfo):
                # Reference to a class or a nested class
                output.update(split_module_names(expr.node.module_name))
            elif expr.fullname is not None and '.' in expr.fullname and not is_suppressed_import:
                # Everything else (that is not a silenced import within a class)
                output.add(expr.fullname.rsplit('.', 1)[0])
            break
        elif isinstance(expr, MemberExpr):
            if isinstance(expr.expr, RefExpr):
                expr = expr.expr
            else:
                break
        else:
            raise AssertionError("Unknown RefExpr subclass: {}".format(type(expr)))
    return output


class Finished(Exception):
    """Raised if we can terminate overload argument check early (no match)."""


class ExpressionChecker(ExpressionVisitor[Type]):
    """Expression type checker.

    This class works closely together with checker.TypeChecker.
    """

    # Some services are provided by a TypeChecker instance.
    chk = None  # type: mypy.checker.TypeChecker
    # This is shared with TypeChecker, but stored also here for convenience.
    msg = None  # type: MessageBuilder
    # Type context for type inference
    type_context = None  # type: List[Optional[Type]]

    strfrm_checker = None  # type: StringFormatterChecker
    plugin = None  # type: Plugin

    def __init__(self,
                 chk: 'mypy.checker.TypeChecker',
                 msg: MessageBuilder,
                 plugin: Plugin) -> None:
        """Construct an expression type checker."""
        self.chk = chk
        self.msg = msg
        self.plugin = plugin
        self.type_context = [None]
        # Temporary overrides for expression types. This is currently
        # used by the union math in overloads.
        # TODO: refactor this to use a pattern similar to one in
        # multiassign_from_union, or maybe even combine the two?
        self.type_overrides = {}  # type: Dict[Expression, Type]
        self.strfrm_checker = StringFormatterChecker(self, self.chk, self.msg)

    def visit_name_expr(self, e: NameExpr) -> Type:
        """Type check a name expression.

        It can be of any kind: local, member or global.
        """
        self.chk.module_refs.update(extract_refexpr_names(e))
        result = self.analyze_ref_expr(e)
        return self.narrow_type_from_binder(e, result)

    def analyze_ref_expr(self, e: RefExpr, lvalue: bool = False) -> Type:
        result = None  # type: Optional[Type]
        node = e.node
        if isinstance(node, Var):
            # Variable reference.
            result = self.analyze_var_ref(node, e)
            if isinstance(result, PartialType):
                result = self.chk.handle_partial_var_type(result, lvalue, node, e)
        elif isinstance(node, FuncDef):
            # Reference to a global function.
            result = function_type(node, self.named_type('builtins.function'))
        elif isinstance(node, OverloadedFuncDef) and node.type is not None:
            # node.type is None when there are multiple definitions of a function
            # and it's decorated by something that is not typing.overload
            result = node.type
        elif isinstance(node, TypeInfo):
            # Reference to a type object.
            result = type_object_type(node, self.named_type)
            if isinstance(result, CallableType) and isinstance(result.ret_type, Instance):
                # We need to set correct line and column
                # TODO: always do this in type_object_type by passing the original context
                result.ret_type.line = e.line
                result.ret_type.column = e.column
            if isinstance(self.type_context[-1], TypeType):
                # This is the type in a Type[] expression, so substitute type
                # variables with Any.
                result = erasetype.erase_typevars(result)
        elif isinstance(node, MypyFile):
            # Reference to a module object.
            try:
                result = self.named_type('types.ModuleType')
            except KeyError:
                # In test cases might 'types' may not be available.
                # Fall back to a dummy 'object' type instead to
                # avoid a crash.
                result = self.named_type('builtins.object')
        elif isinstance(node, Decorator):
            result = self.analyze_var_ref(node.var, e)
        elif isinstance(node, TypeAlias):
            # Something that refers to a type alias appears in runtime context.
            # Note that we suppress bogus errors for alias redefinitions,
            # they are already reported in semanal.py.
            result = self.alias_type_in_runtime_context(node.target, node.alias_tvars,
                                                        node.no_args, e,
                                                        alias_definition=e.is_alias_rvalue
                                                        or lvalue)
        else:
            # Unknown reference; use any type implicitly to avoid
            # generating extra type errors.
            result = AnyType(TypeOfAny.from_error)
        assert result is not None
        return result

    def analyze_var_ref(self, var: Var, context: Context) -> Type:
        if var.type:
            return var.type
        else:
            if not var.is_ready and self.chk.in_checked_function():
                self.chk.handle_cannot_determine_type(var.name(), context)
            # Implicit 'Any' type.
            return AnyType(TypeOfAny.special_form)

    def visit_call_expr(self, e: CallExpr, allow_none_return: bool = False) -> Type:
        """Type check a call expression."""
        if e.analyzed:
            if isinstance(e.analyzed, NamedTupleExpr) and not e.analyzed.is_typed:
                # Type check the arguments, but ignore the results. This relies
                # on the typeshed stubs to type check the arguments.
                self.visit_call_expr_inner(e)
            # It's really a special form that only looks like a call.
            return self.accept(e.analyzed, self.type_context[-1])
        return self.visit_call_expr_inner(e, allow_none_return=allow_none_return)

    def visit_call_expr_inner(self, e: CallExpr, allow_none_return: bool = False) -> Type:
        if isinstance(e.callee, NameExpr) and isinstance(e.callee.node, TypeInfo) and \
                e.callee.node.typeddict_type is not None:
            # Use named fallback for better error messages.
            typeddict_type = e.callee.node.typeddict_type.copy_modified(
                fallback=Instance(e.callee.node, []))
            return self.check_typeddict_call(typeddict_type, e.arg_kinds, e.arg_names, e.args, e)
        if (isinstance(e.callee, NameExpr) and e.callee.name in ('isinstance', 'issubclass')
                and len(e.args) == 2):
            for typ in mypy.checker.flatten(e.args[1]):
                if isinstance(typ, NameExpr):
                    node = None
                    try:
                        node = self.chk.lookup_qualified(typ.name)
                    except KeyError:
                        # Undefined names should already be reported in semantic analysis.
                        pass
                if ((isinstance(typ, IndexExpr)
                        and isinstance(typ.analyzed, (TypeApplication, TypeAliasExpr)))
                        or (isinstance(typ, NameExpr) and node and
                            isinstance(node.node, TypeAlias) and not node.node.no_args)):
                    self.msg.type_arguments_not_allowed(e)
                if isinstance(typ, RefExpr) and isinstance(typ.node, TypeInfo):
                    if typ.node.typeddict_type:
                        self.msg.fail(messages.CANNOT_ISINSTANCE_TYPEDDICT, e)
                    elif typ.node.is_newtype:
                        self.msg.fail(messages.CANNOT_ISINSTANCE_NEWTYPE, e)
        self.try_infer_partial_type(e)
        type_context = None
        if isinstance(e.callee, LambdaExpr):
            formal_to_actual = map_actuals_to_formals(
                e.arg_kinds, e.arg_names,
                e.callee.arg_kinds, e.callee.arg_names,
                lambda i: self.accept(e.args[i]))

            arg_types = [join.join_type_list([self.accept(e.args[j]) for j in formal_to_actual[i]])
                         for i in range(len(e.callee.arg_kinds))]
            type_context = CallableType(arg_types, e.callee.arg_kinds, e.callee.arg_names,
                                        ret_type=self.object_type(),
                                        fallback=self.named_type('builtins.function'))
        callee_type = self.accept(e.callee, type_context, always_allow_any=True)
        if (self.chk.options.disallow_untyped_calls and
                self.chk.in_checked_function() and
                isinstance(callee_type, CallableType)
                and callee_type.implicit):
            return self.msg.untyped_function_call(callee_type, e)
        # Figure out the full name of the callee for plugin lookup.
        object_type = None
        if not isinstance(e.callee, RefExpr):
            fullname = None
        else:
            fullname = e.callee.fullname
            if (isinstance(e.callee.node, TypeAlias) and
                    isinstance(e.callee.node.target, Instance)):
                fullname = e.callee.node.target.type.fullname()
            if (fullname is None
                    and isinstance(e.callee, MemberExpr)
                    and isinstance(callee_type, FunctionLike)):
                # For method calls we include the defining class for the method
                # in the full name (example: 'typing.Mapping.get').
                callee_expr_type = self.chk.type_map.get(e.callee.expr)
                info = None
                # TODO: Support fallbacks of other kinds of types as well?
                if isinstance(callee_expr_type, Instance):
                    info = callee_expr_type.type
                elif isinstance(callee_expr_type, TypedDictType):
                    info = callee_expr_type.fallback.type.get_containing_type_info(e.callee.name)
                if info:
                    fullname = '{}.{}'.format(info.fullname(), e.callee.name)
                    object_type = callee_expr_type
                    # Apply plugin signature hook that may generate a better signature.
                    signature_hook = self.plugin.get_method_signature_hook(fullname)
                    if signature_hook:
                        assert object_type is not None
                        callee_type = self.apply_method_signature_hook(
                            e, callee_type, object_type, signature_hook)
        ret_type = self.check_call_expr_with_callee_type(callee_type, e, fullname, object_type)
        if isinstance(e.callee, RefExpr) and len(e.args) == 2:
            if e.callee.fullname in ('builtins.isinstance', 'builtins.issubclass'):
                self.check_runtime_protocol_test(e)
            if e.callee.fullname == 'builtins.issubclass':
                self.check_protocol_issubclass(e)
        if isinstance(ret_type, UninhabitedType) and not ret_type.ambiguous:
            self.chk.binder.unreachable()
        # Warn on calls to functions that always return None. The check
        # of ret_type is both a common-case optimization and prevents reporting
        # the error in dynamic functions (where it will be Any).
        if (not allow_none_return and isinstance(ret_type, NoneTyp)
                and self.always_returns_none(e.callee)):
            self.chk.msg.does_not_return_value(callee_type, e)
            return AnyType(TypeOfAny.from_error)
        return ret_type

    def always_returns_none(self, node: Expression) -> bool:
        """Check if `node` refers to something explicitly annotated as only returning None."""
        if isinstance(node, RefExpr):
            if self.defn_returns_none(node.node):
                return True
        if isinstance(node, MemberExpr) and node.node is None:  # instance or class attribute
            typ = self.chk.type_map.get(node.expr)
            if isinstance(typ, Instance):
                info = typ.type
            elif (isinstance(typ, CallableType) and typ.is_type_obj() and
                  isinstance(typ.ret_type, Instance)):
                info = typ.ret_type.type
            else:
                return False
            sym = info.get(node.name)
            if sym and self.defn_returns_none(sym.node):
                return True
        return False

    def defn_returns_none(self, defn: Optional[SymbolNode]) -> bool:
        """Check if `defn` can _only_ return None."""
        if isinstance(defn, FuncDef):
            return (isinstance(defn.type, CallableType) and
                    isinstance(defn.type.ret_type, NoneTyp))
        if isinstance(defn, OverloadedFuncDef):
            return all(isinstance(item.type, CallableType) and
                       isinstance(item.type.ret_type, NoneTyp) for item in defn.items)
        if isinstance(defn, Var):
            if (not defn.is_inferred and isinstance(defn.type, CallableType) and
                    isinstance(defn.type.ret_type, NoneTyp)):
                return True
            if isinstance(defn.type, Instance):
                sym = defn.type.type.get('__call__')
                if sym and self.defn_returns_none(sym.node):
                    return True
        return False

    def check_runtime_protocol_test(self, e: CallExpr) -> None:
        for expr in mypy.checker.flatten(e.args[1]):
            tp = self.chk.type_map[expr]
            if (isinstance(tp, CallableType) and tp.is_type_obj() and
                    tp.type_object().is_protocol and
                    not tp.type_object().runtime_protocol):
                self.chk.fail('Only @runtime protocols can be used with'
                              ' instance and class checks', e)

    def check_protocol_issubclass(self, e: CallExpr) -> None:
        for expr in mypy.checker.flatten(e.args[1]):
            tp = self.chk.type_map[expr]
            if (isinstance(tp, CallableType) and tp.is_type_obj() and
                    tp.type_object().is_protocol):
                attr_members = non_method_protocol_members(tp.type_object())
                if attr_members:
                    self.chk.msg.report_non_method_protocol(tp.type_object(),
                                                            attr_members, e)

    def check_typeddict_call(self, callee: TypedDictType,
                             arg_kinds: List[int],
                             arg_names: Sequence[Optional[str]],
                             args: List[Expression],
                             context: Context) -> Type:
        if len(args) >= 1 and all([ak == ARG_NAMED for ak in arg_kinds]):
            # ex: Point(x=42, y=1337)
            assert all(arg_name is not None for arg_name in arg_names)
            item_names = cast(List[str], arg_names)
            item_args = args
            return self.check_typeddict_call_with_kwargs(
                callee, OrderedDict(zip(item_names, item_args)), context)

        if len(args) == 1 and arg_kinds[0] == ARG_POS:
            unique_arg = args[0]
            if isinstance(unique_arg, DictExpr):
                # ex: Point({'x': 42, 'y': 1337})
                return self.check_typeddict_call_with_dict(callee, unique_arg, context)
            if isinstance(unique_arg, CallExpr) and isinstance(unique_arg.analyzed, DictExpr):
                # ex: Point(dict(x=42, y=1337))
                return self.check_typeddict_call_with_dict(callee, unique_arg.analyzed, context)

        if len(args) == 0:
            # ex: EmptyDict()
            return self.check_typeddict_call_with_kwargs(
                callee, OrderedDict(), context)

        self.chk.fail(messages.INVALID_TYPEDDICT_ARGS, context)
        return AnyType(TypeOfAny.from_error)

    def check_typeddict_call_with_dict(self, callee: TypedDictType,
                                       kwargs: DictExpr,
                                       context: Context) -> Type:
        item_args = [item[1] for item in kwargs.items]

        item_names = []  # List[str]
        for item_name_expr, item_arg in kwargs.items:
            if not isinstance(item_name_expr, StrExpr):
                key_context = item_name_expr or item_arg
                self.chk.fail(messages.TYPEDDICT_KEY_MUST_BE_STRING_LITERAL, key_context)
                return AnyType(TypeOfAny.from_error)
            item_names.append(item_name_expr.value)

        return self.check_typeddict_call_with_kwargs(
            callee, OrderedDict(zip(item_names, item_args)), context)

    def check_typeddict_call_with_kwargs(self, callee: TypedDictType,
                                         kwargs: 'OrderedDict[str, Expression]',
                                         context: Context) -> Type:
        if not (callee.required_keys <= set(kwargs.keys()) <= set(callee.items.keys())):
            expected_keys = [key for key in callee.items.keys()
                             if key in callee.required_keys or key in kwargs.keys()]
            actual_keys = kwargs.keys()
            self.msg.unexpected_typeddict_keys(
                callee,
                expected_keys=expected_keys,
                actual_keys=list(actual_keys),
                context=context)
            return AnyType(TypeOfAny.from_error)

        for (item_name, item_expected_type) in callee.items.items():
            if item_name in kwargs:
                item_value = kwargs[item_name]
                self.chk.check_simple_assignment(
                    lvalue_type=item_expected_type, rvalue=item_value, context=item_value,
                    msg=messages.INCOMPATIBLE_TYPES,
                    lvalue_name='TypedDict item "{}"'.format(item_name),
                    rvalue_name='expression')

        return callee

    # Types and methods that can be used to infer partial types.
    item_args = {'builtins.list': ['append'],
                 'builtins.set': ['add', 'discard'],
                 }  # type: ClassVar[Dict[str, List[str]]]
    container_args = {'builtins.list': {'extend': ['builtins.list']},
                      'builtins.dict': {'update': ['builtins.dict']},
                      'builtins.set': {'update': ['builtins.set', 'builtins.list']},
                      }  # type: ClassVar[Dict[str, Dict[str, List[str]]]]

    def try_infer_partial_type(self, e: CallExpr) -> None:
        if isinstance(e.callee, MemberExpr) and isinstance(e.callee.expr, RefExpr):
            var = e.callee.expr.node
            if not isinstance(var, Var):
                return
            partial_types = self.chk.find_partial_types(var)
            if partial_types is not None and not self.chk.current_node_deferred:
                partial_type = var.type
                if (partial_type is None or
                        not isinstance(partial_type, PartialType) or
                        partial_type.type is None):
                    # A partial None type -> can't infer anything.
                    return
                typename = partial_type.type.fullname()
                methodname = e.callee.name
                # Sometimes we can infer a full type for a partial List, Dict or Set type.
                # TODO: Don't infer argument expression twice.
                if (typename in self.item_args and methodname in self.item_args[typename]
                        and e.arg_kinds == [ARG_POS]):
                    item_type = self.accept(e.args[0])
                    full_item_type = UnionType.make_simplified_union(
                        [item_type, partial_type.inner_types[0]])
                    if mypy.checker.is_valid_inferred_type(full_item_type):
                        var.type = self.chk.named_generic_type(typename, [full_item_type])
                        del partial_types[var]
                elif (typename in self.container_args
                      and methodname in self.container_args[typename]
                      and e.arg_kinds == [ARG_POS]):
                    arg_type = self.accept(e.args[0])
                    if isinstance(arg_type, Instance):
                        arg_typename = arg_type.type.fullname()
                        if arg_typename in self.container_args[typename][methodname]:
                            full_item_types = [
                                UnionType.make_simplified_union([item_type, prev_type])
                                for item_type, prev_type
                                in zip(arg_type.args, partial_type.inner_types)
                            ]
                            if all(mypy.checker.is_valid_inferred_type(item_type)
                                   for item_type in full_item_types):
                                var.type = self.chk.named_generic_type(typename,
                                                                       list(full_item_types))
                                del partial_types[var]

    def apply_function_plugin(self,
                              arg_types: List[Type],
                              inferred_ret_type: Type,
                              arg_kinds: List[int],
                              formal_to_actual: List[List[int]],
                              args: List[Expression],
                              num_formals: int,
                              fullname: str,
                              object_type: Optional[Type],
                              context: Context) -> Type:
        """Use special case logic to infer the return type of a specific named function/method.

        Caller must ensure that a plugin hook exists. There are two different cases:

        - If object_type is None, the caller must ensure that a function hook exists
          for fullname.
        - If object_type is not None, the caller must ensure that a method hook exists
          for fullname.

        Return the inferred return type.
        """
        formal_arg_types = [[] for _ in range(num_formals)]  # type: List[List[Type]]
        formal_arg_exprs = [[] for _ in range(num_formals)]  # type: List[List[Expression]]
        for formal, actuals in enumerate(formal_to_actual):
            for actual in actuals:
                formal_arg_types[formal].append(arg_types[actual])
                formal_arg_exprs[formal].append(args[actual])
        if object_type is None:
            # Apply function plugin
            callback = self.plugin.get_function_hook(fullname)
            assert callback is not None  # Assume that caller ensures this
            return callback(
                FunctionContext(formal_arg_types, inferred_ret_type, formal_arg_exprs,
                                context, self.chk))
        else:
            # Apply method plugin
            method_callback = self.plugin.get_method_hook(fullname)
            assert method_callback is not None  # Assume that caller ensures this
            return method_callback(
                MethodContext(object_type, formal_arg_types,
                              inferred_ret_type, formal_arg_exprs,
                              context, self.chk))

    def apply_method_signature_hook(
            self, e: CallExpr, callee: FunctionLike, object_type: Type,
            signature_hook: Callable[[MethodSigContext], CallableType]) -> FunctionLike:
        """Apply a plugin hook that may infer a more precise signature for a method."""
        if isinstance(callee, CallableType):
            arg_kinds = e.arg_kinds
            arg_names = e.arg_names
            args = e.args
            num_formals = len(callee.arg_kinds)
            formal_to_actual = map_actuals_to_formals(
                arg_kinds, arg_names,
                callee.arg_kinds, callee.arg_names,
                lambda i: self.accept(args[i]))
            formal_arg_exprs = [[] for _ in range(num_formals)]  # type: List[List[Expression]]
            for formal, actuals in enumerate(formal_to_actual):
                for actual in actuals:
                    formal_arg_exprs[formal].append(args[actual])
            return signature_hook(
                MethodSigContext(object_type, formal_arg_exprs, callee, e, self.chk))
        else:
            assert isinstance(callee, Overloaded)
            items = []
            for item in callee.items():
                adjusted = self.apply_method_signature_hook(e, item, object_type, signature_hook)
                assert isinstance(adjusted, CallableType)
                items.append(adjusted)
            return Overloaded(items)

    def check_call_expr_with_callee_type(self,
                                         callee_type: Type,
                                         e: CallExpr,
                                         callable_name: Optional[str],
                                         object_type: Optional[Type]) -> Type:
        """Type check call expression.

        The given callee type overrides the type of the callee
        expression.
        """
        return self.check_call(callee_type, e.args, e.arg_kinds, e,
                               e.arg_names, callable_node=e.callee,
                               callable_name=callable_name,
                               object_type=object_type)[0]

    def check_call(self, callee: Type, args: List[Expression],
                   arg_kinds: List[int], context: Context,
                   arg_names: Optional[Sequence[Optional[str]]] = None,
                   callable_node: Optional[Expression] = None,
                   arg_messages: Optional[MessageBuilder] = None,
                   callable_name: Optional[str] = None,
                   object_type: Optional[Type] = None) -> Tuple[Type, Type]:
        """Type check a call.

        Also infer type arguments if the callee is a generic function.

        Return (result type, inferred callee type).

        Arguments:
            callee: type of the called value
            args: actual argument expressions
            arg_kinds: contains nodes.ARG_* constant for each argument in args
                 describing whether the argument is positional, *arg, etc.
            arg_names: names of arguments (optional)
            callable_node: associate the inferred callable type to this node,
                if specified
            arg_messages: TODO
            callable_name: Fully-qualified name of the function/method to call,
                or None if unavailable (examples: 'builtins.open', 'typing.Mapping.get')
            object_type: If callable_name refers to a method, the type of the object
                on which the method is being called
        """
        arg_messages = arg_messages or self.msg
        if isinstance(callee, CallableType):
            if callable_name is None and callee.name:
                callable_name = callee.name
            if callee.is_type_obj() and isinstance(callee.ret_type, Instance):
                callable_name = callee.ret_type.type.fullname()
            if (isinstance(callable_node, RefExpr)
                and callable_node.fullname in ('enum.Enum', 'enum.IntEnum',
                                               'enum.Flag', 'enum.IntFlag')):
                # An Enum() call that failed SemanticAnalyzerPass2.check_enum_call().
                return callee.ret_type, callee

            if (callee.is_type_obj() and callee.type_object().is_abstract
                    # Exception for Type[...]
                    and not callee.from_type_type
                    and not callee.type_object().fallback_to_any):
                type = callee.type_object()
                self.msg.cannot_instantiate_abstract_class(
                    callee.type_object().name(), type.abstract_attributes,
                    context)
            elif (callee.is_type_obj() and callee.type_object().is_protocol
                  # Exception for Type[...]
                  and not callee.from_type_type):
                self.chk.fail('Cannot instantiate protocol class "{}"'
                              .format(callee.type_object().name()), context)

            formal_to_actual = map_actuals_to_formals(
                arg_kinds, arg_names,
                callee.arg_kinds, callee.arg_names,
                lambda i: self.accept(args[i]))

            if callee.is_generic():
                callee = freshen_function_type_vars(callee)
                callee = self.infer_function_type_arguments_using_context(
                    callee, context)
                callee = self.infer_function_type_arguments(
                    callee, args, arg_kinds, formal_to_actual, context)

            arg_types = self.infer_arg_types_in_context(
                callee, args, arg_kinds, formal_to_actual)

            self.check_argument_count(callee, arg_types, arg_kinds,
                                      arg_names, formal_to_actual, context, self.msg)

            self.check_argument_types(arg_types, arg_kinds, callee,
                                      formal_to_actual, context,
                                      messages=arg_messages)

            if (callee.is_type_obj() and (len(arg_types) == 1)
                    and is_equivalent(callee.ret_type, self.named_type('builtins.type'))):
                callee = callee.copy_modified(ret_type=TypeType.make_normalized(arg_types[0]))

            if callable_node:
                # Store the inferred callable type.
                self.chk.store_type(callable_node, callee)

            if (callable_name
                    and ((object_type is None and self.plugin.get_function_hook(callable_name))
                         or (object_type is not None
                             and self.plugin.get_method_hook(callable_name)))):
                ret_type = self.apply_function_plugin(
                    arg_types, callee.ret_type, arg_kinds, formal_to_actual,
                    args, len(callee.arg_types), callable_name, object_type, context)
                callee = callee.copy_modified(ret_type=ret_type)
            return callee.ret_type, callee
        elif isinstance(callee, Overloaded):
            arg_types = self.infer_arg_types_in_empty_context(args)
            return self.check_overload_call(callee=callee,
                                            args=args,
                                            arg_types=arg_types,
                                            arg_kinds=arg_kinds,
                                            arg_names=arg_names,
                                            callable_name=callable_name,
                                            object_type=object_type,
                                            context=context,
                                            arg_messages=arg_messages)
        elif isinstance(callee, AnyType) or not self.chk.in_checked_function():
            self.infer_arg_types_in_empty_context(args)
            if isinstance(callee, AnyType):
                return (AnyType(TypeOfAny.from_another_any, source_any=callee),
                        AnyType(TypeOfAny.from_another_any, source_any=callee))
            else:
                return AnyType(TypeOfAny.special_form), AnyType(TypeOfAny.special_form)
        elif isinstance(callee, UnionType):
            self.msg.disable_type_names += 1
            results = [self.check_call(subtype, args, arg_kinds, context, arg_names,
                                       arg_messages=arg_messages)
                       for subtype in callee.relevant_items()]
            self.msg.disable_type_names -= 1
            return (UnionType.make_simplified_union([res[0] for res in results]),
                    callee)
        elif isinstance(callee, Instance):
            call_function = analyze_member_access('__call__', callee, context,
                                                  False, False, False, self.named_type,
                                                  self.not_ready_callback, self.msg,
                                                  original_type=callee, chk=self.chk)
            return self.check_call(call_function, args, arg_kinds, context, arg_names,
                                   callable_node, arg_messages)
        elif isinstance(callee, TypeVarType):
            return self.check_call(callee.upper_bound, args, arg_kinds, context, arg_names,
                                   callable_node, arg_messages)
        elif isinstance(callee, TypeType):
            # Pass the original Type[] as context since that's where errors should go.
            item = self.analyze_type_type_callee(callee.item, callee)
            return self.check_call(item, args, arg_kinds, context, arg_names,
                                   callable_node, arg_messages)
        elif isinstance(callee, TupleType):
            return self.check_call(callee.fallback, args, arg_kinds, context,
                                   arg_names, callable_node, arg_messages, callable_name,
                                   object_type)
        else:
            return self.msg.not_callable(callee, context), AnyType(TypeOfAny.from_error)

    def analyze_type_type_callee(self, item: Type, context: Context) -> Type:
        """Analyze the callee X in X(...) where X is Type[item].

        Return a Y that we can pass to check_call(Y, ...).
        """
        if isinstance(item, AnyType):
            return AnyType(TypeOfAny.from_another_any, source_any=item)
        if isinstance(item, Instance):
            res = type_object_type(item.type, self.named_type)
            if isinstance(res, CallableType):
                res = res.copy_modified(from_type_type=True)
            return expand_type_by_instance(res, item)
        if isinstance(item, UnionType):
            return UnionType([self.analyze_type_type_callee(tp, context)
                              for tp in item.relevant_items()], item.line)
        if isinstance(item, TypeVarType):
            # Pretend we're calling the typevar's upper bound,
            # i.e. its constructor (a poor approximation for reality,
            # but better than AnyType...), but replace the return type
            # with typevar.
            callee = self.analyze_type_type_callee(item.upper_bound,
                                                   context)  # type: Optional[Type]
            if isinstance(callee, CallableType):
                callee = callee.copy_modified(ret_type=item)
            elif isinstance(callee, Overloaded):
                callee = Overloaded([c.copy_modified(ret_type=item)
                                     for c in callee.items()])
            if callee:
                return callee
        # We support Type of namedtuples but not of tuples in general
        if isinstance(item, TupleType) and item.fallback.type.fullname() != 'builtins.tuple':
            return self.analyze_type_type_callee(item.fallback, context)

        self.msg.unsupported_type_type(item, context)
        return AnyType(TypeOfAny.from_error)

    def infer_arg_types_in_empty_context(self, args: List[Expression]) -> List[Type]:
        """Infer argument expression types in an empty context.

        In short, we basically recurse on each argument without considering
        in what context the argument was called.
        """
        res = []  # type: List[Type]

        for arg in args:
            arg_type = self.accept(arg)
            if has_erased_component(arg_type):
                res.append(NoneTyp())
            else:
                res.append(arg_type)
        return res

    def infer_arg_types_in_context(
            self, callee: CallableType, args: List[Expression], arg_kinds: List[int],
            formal_to_actual: List[List[int]]) -> List[Type]:
        """Infer argument expression types using a callable type as context.

        For example, if callee argument 2 has type List[int], infer the
        argument expression with List[int] type context.

        Returns the inferred types of *actual arguments*.
        """
        res = [None] * len(args)  # type: List[Optional[Type]]

        for i, actuals in enumerate(formal_to_actual):
            for ai in actuals:
                if arg_kinds[ai] not in (nodes.ARG_STAR, nodes.ARG_STAR2):
                    res[ai] = self.accept(args[ai], callee.arg_types[i])

        # Fill in the rest of the argument types.
        for i, t in enumerate(res):
            if not t:
                res[i] = self.accept(args[i])
        assert all(tp is not None for tp in res)
        return cast(List[Type], res)

    def infer_function_type_arguments_using_context(
            self, callable: CallableType, error_context: Context) -> CallableType:
        """Unify callable return type to type context to infer type vars.

        For example, if the return type is set[t] where 't' is a type variable
        of callable, and if the context is set[int], return callable modified
        by substituting 't' with 'int'.
        """
        ctx = self.type_context[-1]
        if not ctx:
            return callable
        # The return type may have references to type metavariables that
        # we are inferring right now. We must consider them as indeterminate
        # and they are not potential results; thus we replace them with the
        # special ErasedType type. On the other hand, class type variables are
        # valid results.
        erased_ctx = replace_meta_vars(ctx, ErasedType())
        ret_type = callable.ret_type
        if is_optional(ret_type) and is_optional(ctx):
            # If both the context and the return type are optional, unwrap the optional,
            # since in 99% cases this is what a user expects. In other words, we replace
            #     Optional[T] <: Optional[int]
            # with
            #     T <: int
            # while the former would infer T <: Optional[int].
            ret_type = remove_optional(ret_type)
            erased_ctx = remove_optional(erased_ctx)
            #
            # TODO: Instead of this hack and the one below, we need to use outer and
            # inner contexts at the same time. This is however not easy because of two
            # reasons:
            #   * We need to support constraints like [1 <: 2, 2 <: X], i.e. with variables
            #     on both sides. (This is not too hard.)
            #   * We need to update all the inference "infrastructure", so that all
            #     variables in an expression are inferred at the same time.
            #     (And this is hard, also we need to be careful with lambdas that require
            #     two passes.)
        if isinstance(ret_type, TypeVarType) and not is_invariant_instance(ctx):
            # Another special case: the return type is a type variable. If it's unrestricted,
            # we could infer a too general type for the type variable if we use context,
            # and this could result in confusing and spurious type errors elsewhere.
            #
            # Give up and just use function arguments for type inference. As an exception,
            # if the context is an invariant instance type, actually use it as context, as
            # this *seems* to usually be the reasonable thing to do.
            #
            # See also github issues #462 and #360.
            return callable.copy_modified()
        args = infer_type_arguments(callable.type_var_ids(), ret_type, erased_ctx)
        # Only substitute non-Uninhabited and non-erased types.
        new_args = []  # type: List[Optional[Type]]
        for arg in args:
            if has_uninhabited_component(arg) or has_erased_component(arg):
                new_args.append(None)
            else:
                new_args.append(arg)
        # Don't show errors after we have only used the outer context for inference.
        # We will use argument context to infer more variables.
        return self.apply_generic_arguments(callable, new_args, error_context,
                                            skip_unsatisfied=True)

    def infer_function_type_arguments(self, callee_type: CallableType,
                                      args: List[Expression],
                                      arg_kinds: List[int],
                                      formal_to_actual: List[List[int]],
                                      context: Context) -> CallableType:
        """Infer the type arguments for a generic callee type.

        Infer based on the types of arguments.

        Return a derived callable type that has the arguments applied.
        """
        if self.chk.in_checked_function():
            # Disable type errors during type inference. There may be errors
            # due to partial available context information at this time, but
            # these errors can be safely ignored as the arguments will be
            # inferred again later.
            self.msg.disable_errors()

            arg_types = self.infer_arg_types_in_context(
                callee_type, args, arg_kinds, formal_to_actual)

            self.msg.enable_errors()

            arg_pass_nums = self.get_arg_infer_passes(
                callee_type.arg_types, formal_to_actual, len(args))

            pass1_args = []  # type: List[Optional[Type]]
            for i, arg in enumerate(arg_types):
                if arg_pass_nums[i] > 1:
                    pass1_args.append(None)
                else:
                    pass1_args.append(arg)

            inferred_args = infer_function_type_arguments(
                callee_type, pass1_args, arg_kinds, formal_to_actual,
                strict=self.chk.in_checked_function())

            if 2 in arg_pass_nums:
                # Second pass of type inference.
                (callee_type,
                 inferred_args) = self.infer_function_type_arguments_pass2(
                    callee_type, args, arg_kinds, formal_to_actual,
                    inferred_args, context)

            if callee_type.special_sig == 'dict' and len(inferred_args) == 2 and (
                    ARG_NAMED in arg_kinds or ARG_STAR2 in arg_kinds):
                # HACK: Infer str key type for dict(...) with keyword args. The type system
                #       can't represent this so we special case it, as this is a pretty common
                #       thing. This doesn't quite work with all possible subclasses of dict
                #       if they shuffle type variables around, as we assume that there is a 1-1
                #       correspondence with dict type variables. This is a marginal issue and
                #       a little tricky to fix so it's left unfixed for now.
                first_arg = inferred_args[0]
                if isinstance(first_arg, (NoneTyp, UninhabitedType)):
                    inferred_args[0] = self.named_type('builtins.str')
                elif not first_arg or not is_subtype(self.named_type('builtins.str'), first_arg):
                    self.msg.fail(messages.KEYWORD_ARGUMENT_REQUIRES_STR_KEY_TYPE,
                                  context)
        else:
            # In dynamically typed functions use implicit 'Any' types for
            # type variables.
            inferred_args = [AnyType(TypeOfAny.unannotated)] * len(callee_type.variables)
        return self.apply_inferred_arguments(callee_type, inferred_args,
                                             context)

    def infer_function_type_arguments_pass2(
            self, callee_type: CallableType,
            args: List[Expression],
            arg_kinds: List[int],
            formal_to_actual: List[List[int]],
            old_inferred_args: Sequence[Optional[Type]],
            context: Context) -> Tuple[CallableType, List[Optional[Type]]]:
        """Perform second pass of generic function type argument inference.

        The second pass is needed for arguments with types such as Callable[[T], S],
        where both T and S are type variables, when the actual argument is a
        lambda with inferred types.  The idea is to infer the type variable T
        in the first pass (based on the types of other arguments).  This lets
        us infer the argument and return type of the lambda expression and
        thus also the type variable S in this second pass.

        Return (the callee with type vars applied, inferred actual arg types).
        """
        # None or erased types in inferred types mean that there was not enough
        # information to infer the argument. Replace them with None values so
        # that they are not applied yet below.
        inferred_args = list(old_inferred_args)
        for i, arg in enumerate(inferred_args):
            if isinstance(arg, (NoneTyp, UninhabitedType)) or has_erased_component(arg):
                inferred_args[i] = None
        callee_type = self.apply_generic_arguments(callee_type, inferred_args, context)

        arg_types = self.infer_arg_types_in_context(
            callee_type, args, arg_kinds, formal_to_actual)

        inferred_args = infer_function_type_arguments(
            callee_type, arg_types, arg_kinds, formal_to_actual)

        return callee_type, inferred_args

    def get_arg_infer_passes(self, arg_types: List[Type],
                             formal_to_actual: List[List[int]],
                             num_actuals: int) -> List[int]:
        """Return pass numbers for args for two-pass argument type inference.

        For each actual, the pass number is either 1 (first pass) or 2 (second
        pass).

        Two-pass argument type inference primarily lets us infer types of
        lambdas more effectively.
        """
        res = [1] * num_actuals
        for i, arg in enumerate(arg_types):
            if arg.accept(ArgInferSecondPassQuery()):
                for j in formal_to_actual[i]:
                    res[j] = 2
        return res

    def apply_inferred_arguments(self, callee_type: CallableType,
                                 inferred_args: Sequence[Optional[Type]],
                                 context: Context) -> CallableType:
        """Apply inferred values of type arguments to a generic function.

        Inferred_args contains the values of function type arguments.
        """
        # Report error if some of the variables could not be solved. In that
        # case assume that all variables have type Any to avoid extra
        # bogus error messages.
        for i, inferred_type in enumerate(inferred_args):
            if not inferred_type or has_erased_component(inferred_type):
                # Could not infer a non-trivial type for a type variable.
                self.msg.could_not_infer_type_arguments(
                    callee_type, i + 1, context)
                inferred_args = [AnyType(TypeOfAny.from_error)] * len(inferred_args)
        # Apply the inferred types to the function type. In this case the
        # return type must be CallableType, since we give the right number of type
        # arguments.
        return self.apply_generic_arguments(callee_type, inferred_args, context)

    def check_argument_count(self, callee: CallableType, actual_types: List[Type],
                             actual_kinds: List[int],
                             actual_names: Optional[Sequence[Optional[str]]],
                             formal_to_actual: List[List[int]],
                             context: Optional[Context],
                             messages: Optional[MessageBuilder]) -> bool:
        """Check that there is a value for all required arguments to a function.

        Also check that there are no duplicate values for arguments. Report found errors
        using 'messages' if it's not None. If 'messages' is given, 'context' must also be given.

        Return False if there were any errors. Otherwise return True
        """
        # TODO(jukka): We could return as soon as we find an error if messages is None.
        formal_kinds = callee.arg_kinds

        # Collect list of all actual arguments matched to formal arguments.
        all_actuals = []  # type: List[int]
        for actuals in formal_to_actual:
            all_actuals.extend(actuals)

        is_unexpected_arg_error = False  # Keep track of errors to avoid duplicate errors.
        ok = True  # False if we've found any error.
        for i, kind in enumerate(actual_kinds):
            if i not in all_actuals and (
                    kind != nodes.ARG_STAR or
                    not is_empty_tuple(actual_types[i])):
                # Extra actual: not matched by a formal argument.
                ok = False
                if kind != nodes.ARG_NAMED:
                    if messages:
                        assert context, "Internal error: messages given without context"
                        messages.too_many_arguments(callee, context)
                else:
                    if messages:
                        assert context, "Internal error: messages given without context"
                        assert actual_names, "Internal error: named kinds without names given"
                        act_name = actual_names[i]
                        assert act_name is not None
                        messages.unexpected_keyword_argument(
                            callee, act_name, context)
                    is_unexpected_arg_error = True
            elif kind == nodes.ARG_STAR and (
                    nodes.ARG_STAR not in formal_kinds):
                actual_type = actual_types[i]
                if isinstance(actual_type, TupleType):
                    if all_actuals.count(i) < len(actual_type.items):
                        # Too many tuple items as some did not match.
                        if messages:
                            assert context, "Internal error: messages given without context"
                            messages.too_many_arguments(callee, context)
                        ok = False
                # *args can be applied even if the function takes a fixed
                # number of positional arguments. This may succeed at runtime.

        for i, kind in enumerate(formal_kinds):
            if kind == nodes.ARG_POS and (not formal_to_actual[i] and
                                          not is_unexpected_arg_error):
                # No actual for a mandatory positional formal.
                if messages:
                    assert context, "Internal error: messages given without context"
                    messages.too_few_arguments(callee, context, actual_names)
                ok = False
            elif kind == nodes.ARG_NAMED and (not formal_to_actual[i] and
                                              not is_unexpected_arg_error):
                # No actual for a mandatory named formal
                if messages:
                    argname = callee.arg_names[i]
                    assert argname is not None
                    assert context, "Internal error: messages given without context"
                    messages.missing_named_argument(callee, context, argname)
                ok = False
            elif kind in [nodes.ARG_POS, nodes.ARG_OPT,
                          nodes.ARG_NAMED, nodes.ARG_NAMED_OPT] and is_duplicate_mapping(
                    formal_to_actual[i], actual_kinds):
                if (self.chk.in_checked_function() or
                        isinstance(actual_types[formal_to_actual[i][0]], TupleType)):
                    if messages:
                        assert context, "Internal error: messages given without context"
                        messages.duplicate_argument_value(callee, i, context)
                    ok = False
            elif (kind in (nodes.ARG_NAMED, nodes.ARG_NAMED_OPT) and formal_to_actual[i] and
                  actual_kinds[formal_to_actual[i][0]] not in [nodes.ARG_NAMED, nodes.ARG_STAR2]):
                # Positional argument when expecting a keyword argument.
                if messages:
                    assert context, "Internal error: messages given without context"
                    messages.too_many_positional_arguments(callee, context)
                ok = False
        return ok

    def check_argument_types(self, arg_types: List[Type], arg_kinds: List[int],
                             callee: CallableType,
                             formal_to_actual: List[List[int]],
                             context: Context,
                             messages: Optional[MessageBuilder] = None,
                             check_arg: Optional[ArgChecker] = None) -> None:
        """Check argument types against a callable type.

        Report errors if the argument types are not compatible.
        """
        messages = messages or self.msg
        check_arg = check_arg or self.check_arg
        # Keep track of consumed tuple *arg items.
        tuple_counter = [0]
        for i, actuals in enumerate(formal_to_actual):
            for actual in actuals:
                arg_type = arg_types[actual]
                if arg_type is None:
                    continue  # Some kind of error was already reported.
                # Check that a *arg is valid as varargs.
                if (arg_kinds[actual] == nodes.ARG_STAR and
                        not self.is_valid_var_arg(arg_type)):
                    messages.invalid_var_arg(arg_type, context)
                if (arg_kinds[actual] == nodes.ARG_STAR2 and
                        not self.is_valid_keyword_var_arg(arg_type)):
                    is_mapping = is_subtype(arg_type, self.chk.named_type('typing.Mapping'))
                    messages.invalid_keyword_var_arg(arg_type, is_mapping, context)
                # Get the type of an individual actual argument (for *args
                # and **args this is the item type, not the collection type).
                if (isinstance(arg_type, TupleType)
                        and tuple_counter[0] >= len(arg_type.items)
                        and arg_kinds[actual] == nodes.ARG_STAR):
                    # The tuple is exhausted. Continue with further arguments.
                    continue
                actual_type = get_actual_type(arg_type, arg_kinds[actual],
                                              tuple_counter)
                check_arg(actual_type, arg_type, arg_kinds[actual],
                          callee.arg_types[i],
                          actual + 1, i + 1, callee, context, messages)

                # There may be some remaining tuple varargs items that haven't
                # been checked yet. Handle them.
                tuplet = arg_types[actual]
                if (callee.arg_kinds[i] == nodes.ARG_STAR and
                        arg_kinds[actual] == nodes.ARG_STAR and
                        isinstance(tuplet, TupleType)):
                    while tuple_counter[0] < len(tuplet.items):
                        actual_type = get_actual_type(arg_type,
                                                      arg_kinds[actual],
                                                      tuple_counter)
                        check_arg(actual_type, arg_type, arg_kinds[actual],
                                  callee.arg_types[i],
                                  actual + 1, i + 1, callee, context, messages)

    def check_arg(self, caller_type: Type, original_caller_type: Type,
                  caller_kind: int,
                  callee_type: Type, n: int, m: int, callee: CallableType,
                  context: Context, messages: MessageBuilder) -> None:
        """Check the type of a single argument in a call."""
        if isinstance(caller_type, DeletedType):
            messages.deleted_as_rvalue(caller_type, context)
        # Only non-abstract non-protocol class can be given where Type[...] is expected...
        elif (isinstance(caller_type, CallableType) and isinstance(callee_type, TypeType) and
              caller_type.is_type_obj() and
              (caller_type.type_object().is_abstract or caller_type.type_object().is_protocol) and
              isinstance(callee_type.item, Instance) and
              (callee_type.item.type.is_abstract or callee_type.item.type.is_protocol)):
            self.msg.concrete_only_call(callee_type, context)
        elif not is_subtype(caller_type, callee_type):
            if self.chk.should_suppress_optional_error([caller_type, callee_type]):
                return
            messages.incompatible_argument(n, m, callee, original_caller_type,
                                           caller_kind, context)
            if (isinstance(original_caller_type, (Instance, TupleType, TypedDictType)) and
                    isinstance(callee_type, Instance) and callee_type.type.is_protocol):
                self.msg.report_protocol_problems(original_caller_type, callee_type, context)
            if (isinstance(callee_type, CallableType) and
                    isinstance(original_caller_type, Instance)):
                call = find_member('__call__', original_caller_type, original_caller_type)
                if call:
                    self.msg.note_call(original_caller_type, call, context)

    def check_overload_call(self,
                            callee: Overloaded,
                            args: List[Expression],
                            arg_types: List[Type],
                            arg_kinds: List[int],
                            arg_names: Optional[Sequence[Optional[str]]],
                            callable_name: Optional[str],
                            object_type: Optional[Type],
                            context: Context,
                            arg_messages: MessageBuilder) -> Tuple[Type, Type]:
        """Checks a call to an overloaded function."""
        # Step 1: Filter call targets to remove ones where the argument counts don't match
        plausible_targets = self.plausible_overload_call_targets(arg_types, arg_kinds,
                                                                 arg_names, callee)

        # Step 2: If the arguments contain a union, we try performing union math first,
        #         instead of picking the first matching overload.
        #         This is because picking the first overload often ends up being too greedy:
        #         for example, when we have a fallback alternative that accepts an unrestricted
        #         typevar. See https://github.com/python/mypy/issues/4063 for related discussion.
        erased_targets = None  # type: Optional[List[CallableType]]
        unioned_result = None  # type: Optional[Tuple[Type, Type]]
        union_interrupted = False  # did we try all union combinations?
        if any(self.real_union(arg) for arg in arg_types):
            unioned_errors = arg_messages.clean_copy()
            try:
                unioned_return = self.union_overload_result(plausible_targets, args,
                                                            arg_types, arg_kinds, arg_names,
                                                            callable_name, object_type,
                                                            context,
                                                            arg_messages=unioned_errors)
            except TooManyUnions:
                union_interrupted = True
            else:
                # Record if we succeeded. Next we need to see if maybe normal procedure
                # gives a narrower type.
                if unioned_return:
                    returns, inferred_types = zip(*unioned_return)
                    # Note that we use `combine_function_signatures` instead of just returning
                    # a union of inferred callables because for example a call
                    # Union[int -> int, str -> str](Union[int, str]) is invalid and
                    # we don't want to introduce internal inconsistencies.
                    unioned_result = (UnionType.make_simplified_union(list(returns),
                                                                      context.line,
                                                                      context.column),
                                      self.combine_function_signatures(inferred_types))

        # Step 3: We try checking each branch one-by-one.
        inferred_result = self.infer_overload_return_type(plausible_targets, args, arg_types,
                                                          arg_kinds, arg_names, callable_name,
                                                          object_type, context, arg_messages)
        # If any of checks succeed, stop early.
        if inferred_result is not None and unioned_result is not None:
            # Both unioned and direct checks succeeded, choose the more precise type.
            if (is_subtype(inferred_result[0], unioned_result[0]) and
                    not isinstance(inferred_result[0], AnyType)):
                return inferred_result
            return unioned_result
        elif unioned_result is not None:
            return unioned_result
        elif inferred_result is not None:
            return inferred_result

        # Step 4: Failure. At this point, we know there is no match. We fall back to trying
        #         to find a somewhat plausible overload target using the erased types
        #         so we can produce a nice error message.
        #
        #         For example, suppose the user passes a value of type 'List[str]' into an
        #         overload with signatures f(x: int) -> int and f(x: List[int]) -> List[int].
        #
        #         Neither alternative matches, but we can guess the user probably wants the
        #         second one.
        erased_targets = self.overload_erased_call_targets(plausible_targets, arg_types,
                                                           arg_kinds, arg_names, context)

        # Step 5: We try and infer a second-best alternative if possible. If not, fall back
        #         to using 'Any'.
        if len(erased_targets) > 0:
            # Pick the first plausible erased target as the fallback
            # TODO: Adjust the error message here to make it clear there was no match.
            #       In order to do this, we need to find a clean way of associating
            #       a note with whatever error message 'self.check_call' will generate.
            #       In particular, the note's line and column numbers need to be the same
            #       as the error's.
            target = erased_targets[0]  # type: Type
        else:
            # There was no plausible match: give up
            target = AnyType(TypeOfAny.from_error)

            if not self.chk.should_suppress_optional_error(arg_types):
                arg_messages.no_variant_matches_arguments(
                    plausible_targets, callee, arg_types, context)

        result = self.check_call(target, args, arg_kinds, context, arg_names,
                                 arg_messages=arg_messages,
                                 callable_name=callable_name,
                                 object_type=object_type)
        if union_interrupted:
            self.chk.msg.note("Not all union combinations were tried"
                              " because there are too many unions", context)
        return result

    def plausible_overload_call_targets(self,
                                        arg_types: List[Type],
                                        arg_kinds: List[int],
                                        arg_names: Optional[Sequence[Optional[str]]],
                                        overload: Overloaded) -> List[CallableType]:
        """Returns all overload call targets that having matching argument counts.

        If the given args contains a star-arg (*arg or **kwarg argument), this method
        will ensure all star-arg overloads appear at the start of the list, instead
        of their usual location.

        The only exception is if the starred argument is something like a Tuple or a
        NamedTuple, which has a definitive "shape". If so, we don't move the corresponding
        alternative to the front since we can infer a more precise match using the original
        order."""

        def has_shape(typ: Type) -> bool:
            # TODO: Once https://github.com/python/mypy/issues/5198 is fixed,
            #       add 'isinstance(typ, TypedDictType)' somewhere below.
            return (isinstance(typ, TupleType)
                    or (isinstance(typ, Instance) and typ.type.is_named_tuple))

        matches = []  # type: List[CallableType]
        star_matches = []  # type: List[CallableType]

        args_have_var_arg = False
        args_have_kw_arg = False
        for kind, typ in zip(arg_kinds, arg_types):
            if kind == ARG_STAR and not has_shape(typ):
                args_have_var_arg = True
            if kind == ARG_STAR2 and not has_shape(typ):
                args_have_kw_arg = True

        for typ in overload.items():
            formal_to_actual = map_actuals_to_formals(arg_kinds, arg_names,
                                                      typ.arg_kinds, typ.arg_names,
                                                      lambda i: arg_types[i])

            if self.check_argument_count(typ, arg_types, arg_kinds, arg_names,
                                         formal_to_actual, None, None):
                if args_have_var_arg and typ.is_var_arg:
                    star_matches.append(typ)
                elif args_have_kw_arg and typ.is_kw_arg:
                    star_matches.append(typ)
                else:
                    matches.append(typ)

        return star_matches + matches

    def infer_overload_return_type(self,
                                   plausible_targets: List[CallableType],
                                   args: List[Expression],
                                   arg_types: List[Type],
                                   arg_kinds: List[int],
                                   arg_names: Optional[Sequence[Optional[str]]],
                                   callable_name: Optional[str],
                                   object_type: Optional[Type],
                                   context: Context,
                                   arg_messages: Optional[MessageBuilder] = None,
                                   ) -> Optional[Tuple[Type, Type]]:
        """Attempts to find the first matching callable from the given list.

        If a match is found, returns a tuple containing the result type and the inferred
        callee type. (This tuple is meant to be eventually returned by check_call.)
        If multiple targets match due to ambiguous Any parameters, returns (AnyType, AnyType).
        If no targets match, returns None.

        Assumes all of the given targets have argument counts compatible with the caller.
        """

        arg_messages = self.msg if arg_messages is None else arg_messages
        matches = []         # type: List[CallableType]
        return_types = []    # type: List[Type]
        inferred_types = []  # type: List[Type]
        args_contain_any = any(map(has_any_type, arg_types))

        for typ in plausible_targets:
            overload_messages = self.msg.clean_copy()
            prev_messages = self.msg
            assert self.msg is self.chk.msg
            self.msg = overload_messages
            self.chk.msg = overload_messages
            try:
                # Passing `overload_messages` as the `arg_messages` parameter doesn't
                # seem to reliably catch all possible errors.
                # TODO: Figure out why
                ret_type, infer_type = self.check_call(
                    callee=typ,
                    args=args,
                    arg_kinds=arg_kinds,
                    arg_names=arg_names,
                    context=context,
                    arg_messages=overload_messages,
                    callable_name=callable_name,
                    object_type=object_type)
            finally:
                self.chk.msg = prev_messages
                self.msg = prev_messages

            is_match = not overload_messages.is_errors()
            if is_match:
                # Return early if possible; otherwise record info so we can
                # check for ambiguity due to 'Any' below.
                if not args_contain_any:
                    return ret_type, infer_type
                matches.append(typ)
                return_types.append(ret_type)
                inferred_types.append(infer_type)

        if len(matches) == 0:
            # No match was found
            return None
        elif any_causes_overload_ambiguity(matches, return_types, arg_types, arg_kinds, arg_names):
            # An argument of type or containing the type 'Any' caused ambiguity.
            # We try returning a precise type if we can. If not, we give up and just return 'Any'.
            if all_same_types(return_types):
                return return_types[0], inferred_types[0]
            elif all_same_types(erase_type(typ) for typ in return_types):
                return erase_type(return_types[0]), erase_type(inferred_types[0])
            else:
                return self.check_call(callee=AnyType(TypeOfAny.special_form),
                                       args=args,
                                       arg_kinds=arg_kinds,
                                       arg_names=arg_names,
                                       context=context,
                                       arg_messages=arg_messages,
                                       callable_name=callable_name,
                                       object_type=object_type)
        else:
            # Success! No ambiguity; return the first match.
            return return_types[0], inferred_types[0]

    def overload_erased_call_targets(self,
                                     plausible_targets: List[CallableType],
                                     arg_types: List[Type],
                                     arg_kinds: List[int],
                                     arg_names: Optional[Sequence[Optional[str]]],
                                     context: Context) -> List[CallableType]:
        """Returns a list of all targets that match the caller after erasing types.

        Assumes all of the given targets have argument counts compatible with the caller.
        """
        matches = []  # type: List[CallableType]
        for typ in plausible_targets:
            if self.erased_signature_similarity(arg_types, arg_kinds, arg_names, typ, context):
                matches.append(typ)
        return matches

    def union_overload_result(self,
                              plausible_targets: List[CallableType],
                              args: List[Expression],
                              arg_types: List[Type],
                              arg_kinds: List[int],
                              arg_names: Optional[Sequence[Optional[str]]],
                              callable_name: Optional[str],
                              object_type: Optional[Type],
                              context: Context,
                              arg_messages: Optional[MessageBuilder] = None,
                              level: int = 0
                              ) -> Optional[List[Tuple[Type, Type]]]:
        """Accepts a list of overload signatures and attempts to match calls by destructuring
        the first union.

        Return a list of (<return type>, <inferred variant type>) if call succeeds for every
        item of the desctructured union. Returns None if there is no match.
        """
        # Step 1: If we are already too deep, then stop immediately. Otherwise mypy might
        # hang for long time because of a weird overload call. The caller will get
        # the exception and generate an appropriate note message, if needed.
        if level >= MAX_UNIONS:
            raise TooManyUnions

        # Step 2: Find position of the first union in arguments. Return the normal inferred
        # type if no more unions left.
        for idx, typ in enumerate(arg_types):
            if self.real_union(typ):
                break
        else:
            # No unions in args, just fall back to normal inference
            with self.type_overrides_set(args, arg_types):
                res = self.infer_overload_return_type(plausible_targets, args, arg_types,
                                                      arg_kinds, arg_names, callable_name,
                                                      object_type, context, arg_messages)
            if res is not None:
                return [res]
            return None

        # Step 3: Try a direct match before splitting to avoid unnecessary union splits
        # and save performance.
        with self.type_overrides_set(args, arg_types):
            direct = self.infer_overload_return_type(plausible_targets, args, arg_types,
                                                     arg_kinds, arg_names, callable_name,
                                                     object_type, context, arg_messages)
        if direct is not None and not isinstance(direct[0], (UnionType, AnyType)):
            # We only return non-unions soon, to avoid greedy match.
            return [direct]

        # Step 4: Split the first remaining union type in arguments into items and
        # try to match each item individually (recursive).
        first_union = arg_types[idx]
        assert isinstance(first_union, UnionType)
        res_items = []
        for item in first_union.relevant_items():
            new_arg_types = arg_types.copy()
            new_arg_types[idx] = item
            sub_result = self.union_overload_result(plausible_targets, args, new_arg_types,
                                                    arg_kinds, arg_names, callable_name,
                                                    object_type, context, arg_messages,
                                                    level + 1)
            if sub_result is not None:
                res_items.extend(sub_result)
            else:
                # Some item doesn't match, return soon.
                return None

        # Step 5: If splitting succeeded, then filter out duplicate items before returning.
        seen = set()  # type: Set[Tuple[Type, Type]]
        result = []
        for pair in res_items:
            if pair not in seen:
                seen.add(pair)
                result.append(pair)
        return result

    def real_union(self, typ: Type) -> bool:
        return isinstance(typ, UnionType) and len(typ.relevant_items()) > 1

    @contextmanager
    def type_overrides_set(self, exprs: Sequence[Expression],
                           overrides: Sequence[Type]) -> Iterator[None]:
        """Set _temporary_ type overrides for given expressions."""
        assert len(exprs) == len(overrides)
        for expr, typ in zip(exprs, overrides):
            self.type_overrides[expr] = typ
        try:
            yield
        finally:
            for expr in exprs:
                del self.type_overrides[expr]

    def combine_function_signatures(self, types: Sequence[Type]) -> Union[AnyType, CallableType]:
        """Accepts a list of function signatures and attempts to combine them together into a
        new CallableType consisting of the union of all of the given arguments and return types.

        If there is at least one non-callable type, return Any (this can happen if there is
        an ambiguity because of Any in arguments).
        """
        assert types, "Trying to merge no callables"
        if not all(isinstance(c, CallableType) for c in types):
            return AnyType(TypeOfAny.special_form)
        callables = cast(Sequence[CallableType], types)
        if len(callables) == 1:
            return callables[0]

        # Note: we are assuming here that if a user uses some TypeVar 'T' in
        # two different functions, they meant for that TypeVar to mean the
        # same thing.
        #
        # This function will make sure that all instances of that TypeVar 'T'
        # refer to the same underlying TypeVarType and TypeVarDef objects to
        # simplify the union-ing logic below.
        #
        # (If the user did *not* mean for 'T' to be consistently bound to the
        # same type in their overloads, well, their code is probably too
        # confusing and ought to be re-written anyways.)
        callables, variables = merge_typevars_in_callables_by_name(callables)

        new_args = [[] for _ in range(len(callables[0].arg_types))]  # type: List[List[Type]]
        new_kinds = list(callables[0].arg_kinds)
        new_returns = []  # type: List[Type]

        too_complex = False
        for target in callables:
            # We fall back to Callable[..., Union[<returns>]] if the functions do not have
            # the exact same signature. The only exception is if one arg is optional and
            # the other is positional: in that case, we continue unioning (and expect a
            # positional arg).
            # TODO: Enhance the merging logic to handle a wider variety of signatures.
            if len(new_kinds) != len(target.arg_kinds):
                too_complex = True
                break
            for i, (new_kind, target_kind) in enumerate(zip(new_kinds, target.arg_kinds)):
                if new_kind == target_kind:
                    continue
                elif new_kind in (ARG_POS, ARG_OPT) and target_kind in (ARG_POS, ARG_OPT):
                    new_kinds[i] = ARG_POS
                else:
                    too_complex = True
                    break

            if too_complex:
                break  # outer loop

            for i, arg in enumerate(target.arg_types):
                new_args[i].append(arg)
            new_returns.append(target.ret_type)

        union_return = UnionType.make_simplified_union(new_returns)
        if too_complex:
            any = AnyType(TypeOfAny.special_form)
            return callables[0].copy_modified(
                arg_types=[any, any],
                arg_kinds=[ARG_STAR, ARG_STAR2],
                arg_names=[None, None],
                ret_type=union_return,
                variables=variables,
                implicit=True)

        final_args = []
        for args_list in new_args:
            new_type = UnionType.make_simplified_union(args_list)
            final_args.append(new_type)

        return callables[0].copy_modified(
            arg_types=final_args,
            arg_kinds=new_kinds,
            ret_type=union_return,
            variables=variables,
            implicit=True)

    def erased_signature_similarity(self, arg_types: List[Type], arg_kinds: List[int],
                                    arg_names: Optional[Sequence[Optional[str]]],
                                    callee: CallableType,
                                    context: Context) -> bool:
        """Determine whether arguments could match the signature at runtime, after
        erasing types."""
        formal_to_actual = map_actuals_to_formals(arg_kinds,
                                                  arg_names,
                                                  callee.arg_kinds,
                                                  callee.arg_names,
                                                  lambda i: arg_types[i])

        if not self.check_argument_count(callee, arg_types, arg_kinds, arg_names,
                                         formal_to_actual, None, None):
            # Too few or many arguments -> no match.
            return False

        def check_arg(caller_type: Type, original_caller_type: Type, caller_kind: int,
                      callee_type: Type, n: int, m: int, callee: CallableType,
                      context: Context, messages: MessageBuilder) -> None:
            if not arg_approximate_similarity(caller_type, callee_type):
                # No match -- exit early since none of the remaining work can change
                # the result.
                raise Finished

        try:
            self.check_argument_types(arg_types, arg_kinds, callee, formal_to_actual,
                                      context=context, check_arg=check_arg)
            return True
        except Finished:
            return False

    def apply_generic_arguments(self, callable: CallableType, types: Sequence[Optional[Type]],
                                context: Context, skip_unsatisfied: bool = False) -> CallableType:
        """Simple wrapper around mypy.applytype.apply_generic_arguments."""
        return applytype.apply_generic_arguments(callable, types, self.msg, context,
                                                 skip_unsatisfied=skip_unsatisfied)

    def visit_member_expr(self, e: MemberExpr, is_lvalue: bool = False) -> Type:
        """Visit member expression (of form e.id)."""
        self.chk.module_refs.update(extract_refexpr_names(e))
        result = self.analyze_ordinary_member_access(e, is_lvalue)
        return self.narrow_type_from_binder(e, result)

    def analyze_ordinary_member_access(self, e: MemberExpr,
                                       is_lvalue: bool) -> Type:
        """Analyse member expression or member lvalue."""
        if e.kind is not None:
            # This is a reference to a module attribute.
            return self.analyze_ref_expr(e)
        else:
            # This is a reference to a non-module attribute.
            original_type = self.accept(e.expr)
            member_type = analyze_member_access(
                e.name, original_type, e, is_lvalue, False, False,
                self.named_type, self.not_ready_callback, self.msg,
                original_type=original_type, chk=self.chk)
            return member_type

    def analyze_external_member_access(self, member: str, base_type: Type,
                                       context: Context) -> Type:
        """Analyse member access that is external, i.e. it cannot
        refer to private definitions. Return the result type.
        """
        # TODO remove; no private definitions in mypy
        return analyze_member_access(member, base_type, context, False, False, False,
                                     self.named_type, self.not_ready_callback, self.msg,
                                     original_type=base_type, chk=self.chk)

    def visit_int_expr(self, e: IntExpr) -> Type:
        """Type check an integer literal (trivial)."""
        return self.named_type('builtins.int')

    def visit_str_expr(self, e: StrExpr) -> Type:
        """Type check a string literal (trivial)."""
        return self.named_type('builtins.str')

    def visit_bytes_expr(self, e: BytesExpr) -> Type:
        """Type check a bytes literal (trivial)."""
        return self.named_type('builtins.bytes')

    def visit_unicode_expr(self, e: UnicodeExpr) -> Type:
        """Type check a unicode literal (trivial)."""
        return self.named_type('builtins.unicode')

    def visit_float_expr(self, e: FloatExpr) -> Type:
        """Type check a float literal (trivial)."""
        return self.named_type('builtins.float')

    def visit_complex_expr(self, e: ComplexExpr) -> Type:
        """Type check a complex literal."""
        return self.named_type('builtins.complex')

    def visit_ellipsis(self, e: EllipsisExpr) -> Type:
        """Type check '...'."""
        if self.chk.options.python_version[0] >= 3:
            return self.named_type('builtins.ellipsis')
        else:
            # '...' is not valid in normal Python 2 code, but it can
            # be used in stubs.  The parser makes sure that we only
            # get this far if we are in a stub, and we can safely
            # return 'object' as ellipsis is special cased elsewhere.
            # The builtins.ellipsis type does not exist in Python 2.
            return self.named_type('builtins.object')

    def visit_op_expr(self, e: OpExpr) -> Type:
        """Type check a binary operator expression."""
        if e.op == 'and' or e.op == 'or':
            return self.check_boolean_op(e, e)
        if e.op == '*' and isinstance(e.left, ListExpr):
            # Expressions of form [...] * e get special type inference.
            return self.check_list_multiply(e)
        if e.op == '%':
            pyversion = self.chk.options.python_version
            if pyversion[0] == 3:
                if isinstance(e.left, BytesExpr) and pyversion[1] >= 5:
                    return self.strfrm_checker.check_str_interpolation(e.left, e.right)
                if isinstance(e.left, StrExpr):
                    return self.strfrm_checker.check_str_interpolation(e.left, e.right)
            elif pyversion[0] <= 2:
                if isinstance(e.left, (StrExpr, BytesExpr, UnicodeExpr)):
                    return self.strfrm_checker.check_str_interpolation(e.left, e.right)
        left_type = self.accept(e.left)

        if e.op in nodes.op_methods:
            method = self.get_operator_method(e.op)
            result, method_type = self.check_op(method, left_type, e.right, e,
                                                allow_reverse=True)
            e.method_type = method_type
            return result
        else:
            raise RuntimeError('Unknown operator {}'.format(e.op))

    def visit_comparison_expr(self, e: ComparisonExpr) -> Type:
        """Type check a comparison expression.

        Comparison expressions are type checked consecutive-pair-wise
        That is, 'a < b > c == d' is check as 'a < b and b > c and c == d'
        """
        result = None  # type: Optional[Type]

        # Check each consecutive operand pair and their operator
        for left, right, operator in zip(e.operands, e.operands[1:], e.operators):
            left_type = self.accept(left)

            method_type = None  # type: Optional[mypy.types.Type]

            if operator == 'in' or operator == 'not in':
                right_type = self.accept(right)  # always validate the right operand

                # Keep track of whether we get type check errors (these won't be reported, they
                # are just to verify whether something is valid typing wise).
                local_errors = self.msg.copy()
                local_errors.disable_count = 0
                sub_result, method_type = self.check_op_local_by_name('__contains__', right_type,
                                                                      left, e, local_errors)
                if isinstance(right_type, PartialType):
                    # We don't really know if this is an error or not, so just shut up.
                    pass
                elif (local_errors.is_errors() and
                    # is_valid_var_arg is True for any Iterable
                        self.is_valid_var_arg(right_type)):
                    _, itertype = self.chk.analyze_iterable_item_type(right)
                    method_type = CallableType(
                        [left_type],
                        [nodes.ARG_POS],
                        [None],
                        self.bool_type(),
                        self.named_type('builtins.function'))
                    sub_result = self.bool_type()
                    if not is_subtype(left_type, itertype):
                        self.msg.unsupported_operand_types('in', left_type, right_type, e)
                else:
                    self.msg.add_errors(local_errors)
                if operator == 'not in':
                    sub_result = self.bool_type()
            elif operator in nodes.op_methods:
                method = self.get_operator_method(operator)
                sub_result, method_type = self.check_op(method, left_type, right, e,
                                                    allow_reverse=True)

            elif operator == 'is' or operator == 'is not':
                self.accept(right)  # validate the right operand
                sub_result = self.bool_type()
                method_type = None
            else:
                raise RuntimeError('Unknown comparison operator {}'.format(operator))

            e.method_types.append(method_type)

            #  Determine type of boolean-and of result and sub_result
            if result is None:
                result = sub_result
            else:
                result = join.join_types(result, sub_result)

        assert result is not None
        return result

    def get_operator_method(self, op: str) -> str:
        if op == '/' and self.chk.options.python_version[0] == 2:
            # TODO also check for "from __future__ import division"
            return '__div__'
        else:
            return nodes.op_methods[op]

    def check_op_local_by_name(self,
                               method: str,
                               base_type: Type,
                               arg: Expression,
                               context: Context,
                               local_errors: MessageBuilder) -> Tuple[Type, Type]:
        """Type check a binary operation which maps to a method call.

        Return tuple (result type, inferred operator method type).
        """
        method_type = analyze_member_access(method, base_type, context, False, False, True,
                                            self.named_type, self.not_ready_callback, local_errors,
                                            original_type=base_type, chk=self.chk)
        return self.check_op_local(method, method_type, base_type, arg, context, local_errors)

    def check_op_local(self,
                       method_name: str,
                       method_type: Type,
                       base_type: Type,
                       arg: Expression,
                       context: Context,
                       local_errors: MessageBuilder) -> Tuple[Type, Type]:
        """Type check a binary operation using the (assumed) type of the operator method.

        Return tuple (result type, inferred operator method type).
        """
        callable_name = None
        object_type = None
        if isinstance(base_type, Instance):
            # TODO: Find out in which class the method was defined originally?
            # TODO: Support non-Instance types.
            callable_name = '{}.{}'.format(base_type.type.fullname(), method_name)
            object_type = base_type
        return self.check_call(method_type, [arg], [nodes.ARG_POS],
                               context, arg_messages=local_errors,
                               callable_name=callable_name, object_type=object_type)

    def check_op_reversible(self,
                            op_name: str,
                            left_type: Type,
                            left_expr: Expression,
                            right_type: Type,
                            right_expr: Expression,
                            context: Context,
                            msg: MessageBuilder) -> Tuple[Type, Type]:
        def make_local_errors() -> MessageBuilder:
            """Creates a new MessageBuilder object."""
            local_errors = msg.clean_copy()
            local_errors.disable_count = 0
            return local_errors

        def lookup_operator(op_name: str, base_type: Type) -> Optional[Type]:
            """Looks up the given operator and returns the corresponding type,
            if it exists."""
            local_errors = make_local_errors()

            # TODO: Remove this call and rely just on analyze_member_access
            # Currently, it seems we still need this to correctly deal with
            # things like metaclasses?
            #
            # E.g. see the pythoneval.testMetaclassOpAccessAny test case.
            if not self.has_member(base_type, op_name):
                return None

            member = analyze_member_access(
                name=op_name,
                typ=base_type,
                node=context,
                is_lvalue=False,
                is_super=False,
                is_operator=True,
                builtin_type=self.named_type,
                not_ready_callback=self.not_ready_callback,
                msg=local_errors,
                original_type=base_type,
                chk=self.chk,
            )
            if local_errors.is_errors():
                return None
            else:
                return member

        def lookup_definer(typ: Instance, attr_name: str) -> Optional[str]:
            """Returns the name of the class that contains the actual definition of attr_name.

            So if class A defines foo and class B subclasses A, running
            'get_class_defined_in(B, "foo")` would return the full name of A.

            However, if B were to override and redefine foo, that method call would
            return the full name of B instead.

            If the attr name is not present in the given class or its MRO, returns None.
            """
            for cls in typ.type.mro:
                if cls.names.get(attr_name):
                    return cls.fullname()
            return None

        # If either the LHS or the RHS are Any, we can't really concluding anything
        # about the operation since the Any type may or may not define an
        # __op__ or __rop__ method. So, we punt and return Any instead.

        if isinstance(left_type, AnyType):
            any_type = AnyType(TypeOfAny.from_another_any, source_any=left_type)
            return any_type, any_type
        if isinstance(right_type, AnyType):
            any_type = AnyType(TypeOfAny.from_another_any, source_any=right_type)
            return any_type, any_type

        # STEP 1:
        # We start by getting the __op__ and __rop__ methods, if they exist.

        rev_op_name = self.get_reverse_op_method(op_name)

        left_op = lookup_operator(op_name, left_type)
        right_op = lookup_operator(rev_op_name, right_type)

        # STEP 2a:
        # We figure out in which order Python will call the operator methods. As it
        # turns out, it's not as simple as just trying to call __op__ first and
        # __rop__ second.
        #
        # We store the determined order inside the 'variants_raw' variable,
        # which records tuples containing the method, base type, and the argument.

        bias_right = is_proper_subtype(right_type, left_type)
        if op_name in nodes.op_methods_that_shortcut and is_same_type(left_type, right_type):
            # When we do "A() + A()", for example, Python will only call the __add__ method,
            # never the __radd__ method.
            #
            # This is the case even if the __add__ method is completely missing and the __radd__
            # method is defined.

            variants_raw = [
                (left_op, left_type, right_expr)
            ]
        elif (is_subtype(right_type, left_type)
                and isinstance(left_type, Instance)
                and isinstance(right_type, Instance)
                and lookup_definer(left_type, op_name) != lookup_definer(right_type, rev_op_name)):
            # When we do "A() + B()" where B is a subclass of B, we'll actually try calling
            # B's __radd__ method first, but ONLY if B explicitly defines or overrides the
            # __radd__ method.
            #
            # This mechanism lets subclasses "refine" the expected outcome of the operation, even
            # if they're located on the RHS.

            variants_raw = [
                (right_op, right_type, left_expr),
                (left_op, left_type, right_expr),
            ]
        else:
            # In all other cases, we do the usual thing and call __add__ first and
            # __radd__ second when doing "A() + B()".

            variants_raw = [
                (left_op, left_type, right_expr),
                (right_op, right_type, left_expr),
            ]

        # STEP 2b:
        # When running Python 2, we might also try calling the __cmp__ method.

        is_python_2 = self.chk.options.python_version[0] == 2
        if is_python_2 and op_name in nodes.ops_falling_back_to_cmp:
            cmp_method = nodes.comparison_fallback_method
            left_cmp_op = lookup_operator(cmp_method, left_type)
            right_cmp_op = lookup_operator(cmp_method, right_type)

            if bias_right:
                variants_raw.append((right_cmp_op, right_type, left_expr))
                variants_raw.append((left_cmp_op, left_type, right_expr))
            else:
                variants_raw.append((left_cmp_op, left_type, right_expr))
                variants_raw.append((right_cmp_op, right_type, left_expr))

        # STEP 3:
        # We now filter out all non-existant operators. The 'variants' list contains
        # all operator methods that are actually present, in the order that Python
        # attempts to invoke them.

        variants = [(op, obj, arg) for (op, obj, arg) in variants_raw if op is not None]

        # STEP 4:
        # We now try invoking each one. If an operation succeeds, end early and return
        # the corresponding result. Otherwise, return the result and errors associated
        # with the first entry.

        errors = []
        results = []
        for method, obj, arg in variants:
            local_errors = make_local_errors()
            result = self.check_op_local(op_name, method, obj, arg, context, local_errors)
            if local_errors.is_errors():
                errors.append(local_errors)
                results.append(result)
            else:
                return result

        # STEP 4b:
        # Sometimes, the variants list is empty. In that case, we fall-back to attempting to
        # call the __op__ method (even though it's missing).

        if not variants:
            local_errors = make_local_errors()
            result = self.check_op_local_by_name(
                op_name, left_type, right_expr, context, local_errors)

            if local_errors.is_errors():
                errors.append(local_errors)
                results.append(result)
            else:
                # In theory, we should never enter this case, but it seems
                # we sometimes do, when dealing with Type[...]? E.g. see
                # check-classes.testTypeTypeComparisonWorks.
                #
                # This is probably related to the TODO in lookup_operator(...)
                # up above.
                #
                # TODO: Remove this extra case
                return result

        msg.add_errors(errors[0])
        if len(results) == 1:
            return results[0]
        else:
            error_any = AnyType(TypeOfAny.from_error)
            result = error_any, error_any
            return result

    def check_op(self, method: str, base_type: Type,
                 arg: Expression, context: Context,
                 allow_reverse: bool = False) -> Tuple[Type, Type]:
        """Type check a binary operation which maps to a method call.

        Return tuple (result type, inferred operator method type).
        """

        if allow_reverse:
            left_variants = [base_type]
            if isinstance(base_type, UnionType):
                left_variants = [item for item in base_type.relevant_items()]
            right_type = self.accept(arg)

            # Step 1: We first try leaving the right arguments alone and destructure
            # just the left ones. (Mypy can sometimes perform some more precise inference
            # if we leave the right operands a union -- see testOperatorWithEmptyListAndSum.
            msg = self.msg.clean_copy()
            msg.disable_count = 0
            all_results = []
            all_inferred = []

            for left_possible_type in left_variants:
                result, inferred = self.check_op_reversible(
                    op_name=method,
                    left_type=left_possible_type,
                    left_expr=TempNode(left_possible_type),
                    right_type=right_type,
                    right_expr=arg,
                    context=context,
                    msg=msg)
                all_results.append(result)
                all_inferred.append(inferred)

            if not msg.is_errors():
                results_final = UnionType.make_simplified_union(all_results)
                inferred_final = UnionType.make_simplified_union(all_inferred)
                return results_final, inferred_final

            # Step 2: If that fails, we try again but also destructure the right argument.
            # This is also necessary to make certain edge cases work -- see
            # testOperatorDoubleUnionInterwovenUnionAdd, for example.

            # Note: We want to pass in the original 'arg' for 'left_expr' and 'right_expr'
            # whenever possible so that plugins and similar things can introspect on the original
            # node if possible.
            #
            # We don't do the same for the base expression because it could lead to weird
            # type inference errors -- e.g. see 'testOperatorDoubleUnionSum'.
            # TODO: Can we use `type_overrides_set()` here?
            right_variants = [(right_type, arg)]
            if isinstance(right_type, UnionType):
                right_variants = [(item, TempNode(item)) for item in right_type.relevant_items()]

            msg = self.msg.clean_copy()
            msg.disable_count = 0
            all_results = []
            all_inferred = []

            for left_possible_type in left_variants:
                for right_possible_type, right_expr in right_variants:
                    result, inferred = self.check_op_reversible(
                        op_name=method,
                        left_type=left_possible_type,
                        left_expr=TempNode(left_possible_type),
                        right_type=right_possible_type,
                        right_expr=right_expr,
                        context=context,
                        msg=msg)
                    all_results.append(result)
                    all_inferred.append(inferred)

            if msg.is_errors():
                self.msg.add_errors(msg)
                if len(left_variants) >= 2 and len(right_variants) >= 2:
                    self.msg.warn_both_operands_are_from_unions(context)
                elif len(left_variants) >= 2:
                    self.msg.warn_operand_was_from_union("Left", base_type, context)
                elif len(right_variants) >= 2:
                    self.msg.warn_operand_was_from_union("Right", right_type, context)

            # See the comment in 'check_overload_call' for more details on why
            # we call 'combine_function_signature' instead of just unioning the inferred
            # callable types.
            results_final = UnionType.make_simplified_union(all_results)
            inferred_final = self.combine_function_signatures(all_inferred)
            return results_final, inferred_final
        else:
            return self.check_op_local_by_name(
                method=method,
                base_type=base_type,
                arg=arg,
                context=context,
                local_errors=self.msg,
            )

    def get_reverse_op_method(self, method: str) -> str:
        if method == '__div__' and self.chk.options.python_version[0] == 2:
            return '__rdiv__'
        else:
            return nodes.reverse_op_methods[method]

    def check_boolean_op(self, e: OpExpr, context: Context) -> Type:
        """Type check a boolean operation ('and' or 'or')."""

        # A boolean operation can evaluate to either of the operands.

        # We use the current type context to guide the type inference of of
        # the left operand. We also use the left operand type to guide the type
        # inference of the right operand so that expressions such as
        # '[1] or []' are inferred correctly.
        ctx = self.type_context[-1]
        left_type = self.accept(e.left, ctx)

        assert e.op in ('and', 'or')  # Checked by visit_op_expr

        if e.op == 'and':
            right_map, left_map = self.chk.find_isinstance_check(e.left)
            restricted_left_type = false_only(left_type)
            result_is_left = not left_type.can_be_true
        elif e.op == 'or':
            left_map, right_map = self.chk.find_isinstance_check(e.left)
            restricted_left_type = true_only(left_type)
            result_is_left = not left_type.can_be_false

        if e.right_unreachable:
            right_map = None
        elif e.right_always:
            left_map = None

        # If right_map is None then we know mypy considers the right branch
        # to be unreachable and therefore any errors found in the right branch
        # should be suppressed.
        if right_map is None:
            self.msg.disable_errors()
        try:
            right_type = self.analyze_cond_branch(right_map, e.right, left_type)
        finally:
            if right_map is None:
                self.msg.enable_errors()

        if right_map is None:
            # The boolean expression is statically known to be the left value
            assert left_map is not None  # find_isinstance_check guarantees this
            return left_type
        if left_map is None:
            # The boolean expression is statically known to be the right value
            assert right_map is not None  # find_isinstance_check guarantees this
            return right_type

        if isinstance(restricted_left_type, UninhabitedType):
            # The left operand can never be the result
            return right_type
        elif result_is_left:
            # The left operand is always the result
            return left_type
        else:
            return UnionType.make_simplified_union([restricted_left_type, right_type])

    def check_list_multiply(self, e: OpExpr) -> Type:
        """Type check an expression of form '[...] * e'.

        Type inference is special-cased for this common construct.
        """
        right_type = self.accept(e.right)
        if is_subtype(right_type, self.named_type('builtins.int')):
            # Special case: [...] * <int value>. Use the type context of the
            # OpExpr, since the multiplication does not affect the type.
            left_type = self.accept(e.left, type_context=self.type_context[-1])
        else:
            left_type = self.accept(e.left)
        result, method_type = self.check_op('__mul__', left_type, e.right, e)
        e.method_type = method_type
        return result

    def visit_unary_expr(self, e: UnaryExpr) -> Type:
        """Type check an unary operation ('not', '-', '+' or '~')."""
        operand_type = self.accept(e.expr)
        op = e.op
        if op == 'not':
            result = self.bool_type()  # type: Type
        else:
            method = nodes.unary_op_methods[op]
            method_type = self.analyze_external_member_access(method, operand_type, e)
            result, method_type = self.check_call(method_type, [], [], e)
            e.method_type = method_type
        return result

    def visit_index_expr(self, e: IndexExpr) -> Type:
        """Type check an index expression (base[index]).

        It may also represent type application.
        """
        result = self.visit_index_expr_helper(e)
        return self.narrow_type_from_binder(e, result)

    def visit_index_expr_helper(self, e: IndexExpr) -> Type:
        if e.analyzed:
            # It's actually a type application.
            return self.accept(e.analyzed)
        left_type = self.accept(e.base)
        if isinstance(left_type, TupleType) and self.chk.in_checked_function():
            # Special case for tuples. They return a more specific type when
            # indexed by an integer literal.
            index = e.index
            if isinstance(index, SliceExpr):
                return self.visit_tuple_slice_helper(left_type, index)

            n = self._get_value(index)
            if n is not None:
                if n < 0:
                    n += len(left_type.items)
                if n >= 0 and n < len(left_type.items):
                    return left_type.items[n]
                else:
                    self.chk.fail(messages.TUPLE_INDEX_OUT_OF_RANGE, e)
                    return AnyType(TypeOfAny.from_error)
            else:
                return self.nonliteral_tuple_index_helper(left_type, index)
        elif isinstance(left_type, TypedDictType):
            return self.visit_typeddict_index_expr(left_type, e.index)
        elif (isinstance(left_type, CallableType)
              and left_type.is_type_obj() and left_type.type_object().is_enum):
            return self.visit_enum_index_expr(left_type.type_object(), e.index, e)
        else:
            result, method_type = self.check_op('__getitem__', left_type, e.index, e)
            e.method_type = method_type
            return result

    def visit_tuple_slice_helper(self, left_type: TupleType, slic: SliceExpr) -> Type:
        begin = None
        end = None
        stride = None

        if slic.begin_index:
            begin = self._get_value(slic.begin_index)
            if begin is None:
                return self.nonliteral_tuple_index_helper(left_type, slic)

        if slic.end_index:
            end = self._get_value(slic.end_index)
            if end is None:
                return self.nonliteral_tuple_index_helper(left_type, slic)

        if slic.stride:
            stride = self._get_value(slic.stride)
            if stride is None:
                return self.nonliteral_tuple_index_helper(left_type, slic)

        return left_type.slice(begin, stride, end)

    def nonliteral_tuple_index_helper(self, left_type: TupleType, index: Expression) -> Type:
        index_type = self.accept(index)
        expected_type = UnionType.make_union([self.named_type('builtins.int'),
                                              self.named_type('builtins.slice')])
        if not self.chk.check_subtype(index_type, expected_type, index,
                                      messages.INVALID_TUPLE_INDEX_TYPE,
                                      'actual type', 'expected type'):
            return AnyType(TypeOfAny.from_error)
        else:
            return UnionType.make_simplified_union(left_type.items)

    def _get_value(self, index: Expression) -> Optional[int]:
        if isinstance(index, IntExpr):
            return index.value
        elif isinstance(index, UnaryExpr):
            if index.op == '-':
                operand = index.expr
                if isinstance(operand, IntExpr):
                    return -1 * operand.value
        return None

    def visit_typeddict_index_expr(self, td_type: TypedDictType, index: Expression) -> Type:
        if not isinstance(index, (StrExpr, UnicodeExpr)):
            self.msg.typeddict_key_must_be_string_literal(td_type, index)
            return AnyType(TypeOfAny.from_error)
        item_name = index.value

        item_type = td_type.items.get(item_name)
        if item_type is None:
            self.msg.typeddict_key_not_found(td_type, item_name, index)
            return AnyType(TypeOfAny.from_error)
        return item_type

    def visit_enum_index_expr(self, enum_type: TypeInfo, index: Expression,
                              context: Context) -> Type:
        string_type = self.named_type('builtins.str')  # type: Type
        if self.chk.options.python_version[0] < 3:
            string_type = UnionType.make_union([string_type,
                                                self.named_type('builtins.unicode')])
        self.chk.check_subtype(self.accept(index), string_type, context,
                               "Enum index should be a string", "actual index type")
        return Instance(enum_type, [])

    def visit_cast_expr(self, expr: CastExpr) -> Type:
        """Type check a cast expression."""
        source_type = self.accept(expr.expr, type_context=AnyType(TypeOfAny.special_form),
                                  allow_none_return=True, always_allow_any=True)
        target_type = expr.type
        options = self.chk.options
        if options.warn_redundant_casts and is_same_type(source_type, target_type):
            self.msg.redundant_cast(target_type, expr)
        if options.disallow_any_unimported and has_any_from_unimported_type(target_type):
            self.msg.unimported_type_becomes_any("Target type of cast", target_type, expr)
        check_for_explicit_any(target_type, self.chk.options, self.chk.is_typeshed_stub, self.msg,
                               context=expr)
        return target_type

    def visit_reveal_expr(self, expr: RevealExpr) -> Type:
        """Type check a reveal_type expression."""
        if expr.kind == REVEAL_TYPE:
            assert expr.expr is not None
            revealed_type = self.accept(expr.expr, type_context=self.type_context[-1])
            if not self.chk.current_node_deferred:
                self.msg.reveal_type(revealed_type, expr)
                if not self.chk.in_checked_function():
                    self.msg.note("'reveal_type' always outputs 'Any' in unchecked functions",
                                  expr)
            return revealed_type
        else:
            # REVEAL_LOCALS
            if not self.chk.current_node_deferred:
                # the RevealExpr contains a local_nodes attribute,
                # calculated at semantic analysis time. Use it to pull out the
                # corresponding subset of variables in self.chk.type_map
                names_to_types = {
                    var_node.name(): var_node.type for var_node in expr.local_nodes
                } if expr.local_nodes is not None else {}

                self.msg.reveal_locals(names_to_types, expr)
            return NoneTyp()

    def visit_type_application(self, tapp: TypeApplication) -> Type:
        """Type check a type application (expr[type, ...]).

        There are two different options here, depending on whether expr refers
        to a type alias or directly to a generic class. In the first case we need
        to use a dedicated function typeanal.expand_type_aliases. This
        is due to the fact that currently type aliases machinery uses
        unbound type variables, while normal generics use bound ones;
        see TypeAlias docstring for more details.
        """
        if isinstance(tapp.expr, RefExpr) and isinstance(tapp.expr.node, TypeAlias):
            # Subscription of a (generic) alias in runtime context, expand the alias.
            target = tapp.expr.node.target
            all_vars = tapp.expr.node.alias_tvars
            item = expand_type_alias(target, all_vars, tapp.types, self.chk.fail,
                                     tapp.expr.node.no_args, tapp)
            if isinstance(item, Instance):
                tp = type_object_type(item.type, self.named_type)
                return self.apply_type_arguments_to_callable(tp, item.args, tapp)
            else:
                self.chk.fail(messages.ONLY_CLASS_APPLICATION, tapp)
                return AnyType(TypeOfAny.from_error)
        # Type application of a normal generic class in runtime context.
        # This is typically used as `x = G[int]()`.
        tp = self.accept(tapp.expr)
        if isinstance(tp, (CallableType, Overloaded)):
            if not tp.is_type_obj():
                self.chk.fail(messages.ONLY_CLASS_APPLICATION, tapp)
            return self.apply_type_arguments_to_callable(tp, tapp.types, tapp)
        if isinstance(tp, AnyType):
            return AnyType(TypeOfAny.from_another_any, source_any=tp)
        return AnyType(TypeOfAny.special_form)

    def visit_type_alias_expr(self, alias: TypeAliasExpr) -> Type:
        """Right hand side of a type alias definition.

        It has the same type as if the alias itself was used in a runtime context.
        For example, here:

            A = reveal_type(List[T])
            reveal_type(A)

        both `reveal_type` instances will reveal the same type `def (...) -> builtins.list[Any]`.
        Note that type variables are implicitly substituted with `Any`.
        """
        return self.alias_type_in_runtime_context(alias.type, alias.tvars, alias.no_args,
                                                  alias, alias_definition=True)

    def alias_type_in_runtime_context(self, target: Type, alias_tvars: List[str],
                                      no_args: bool, ctx: Context,
                                      *,
                                      alias_definition: bool = False) -> Type:
        """Get type of a type alias (could be generic) in a runtime expression.

        Note that this function can be called only if the alias appears _not_
        as a target of type application, which is treated separately in the
        visit_type_application method. Some examples where this method is called are
        casts and instantiation:

            class LongName(Generic[T]): ...
            A = LongName[int]

            x = A()
            y = cast(A, ...)
        """
        if isinstance(target, Instance) and target.invalid:
            # An invalid alias, error already has been reported
            return AnyType(TypeOfAny.from_error)
        # If this is a generic alias, we set all variables to `Any`.
        # For example:
        #     A = List[Tuple[T, T]]
        #     x = A() <- same as List[Tuple[Any, Any]], see PEP 484.
        item = set_any_tvars(target, alias_tvars, ctx.line, ctx.column)
        if isinstance(item, Instance):
            # Normally we get a callable type (or overloaded) with .is_type_obj() true
            # representing the class's constructor
            tp = type_object_type(item.type, self.named_type)
            if no_args:
                return tp
            return self.apply_type_arguments_to_callable(tp, item.args, ctx)
        elif (isinstance(item, TupleType) and
              # Tuple[str, int]() fails at runtime, only named tuples and subclasses work.
              item.fallback.type.fullname() != 'builtins.tuple'):
            return type_object_type(item.fallback.type, self.named_type)
        elif isinstance(item, AnyType):
            return AnyType(TypeOfAny.from_another_any, source_any=item)
        else:
            if alias_definition:
                return AnyType(TypeOfAny.special_form)
            # This type is invalid in most runtime contexts.
            self.msg.alias_invalid_in_runtime_context(item, ctx)
            return AnyType(TypeOfAny.from_error)

    def apply_type_arguments_to_callable(self, tp: Type, args: List[Type], ctx: Context) -> Type:
        """Apply type arguments to a generic callable type coming from a type object.

        This will first perform type arguments count checks, report the
        error as needed, and return the correct kind of Any. As a special
        case this returns Any for non-callable types, because if type object type
        is not callable, then an error should be already reported.
        """
        if isinstance(tp, CallableType):
            if len(tp.variables) != len(args):
                self.msg.incompatible_type_application(len(tp.variables),
                                                       len(args), ctx)
                return AnyType(TypeOfAny.from_error)
            return self.apply_generic_arguments(tp, args, ctx)
        if isinstance(tp, Overloaded):
            for it in tp.items():
                if len(it.variables) != len(args):
                    self.msg.incompatible_type_application(len(it.variables),
                                                           len(args), ctx)
                    return AnyType(TypeOfAny.from_error)
            return Overloaded([self.apply_generic_arguments(it, args, ctx)
                               for it in tp.items()])
        return AnyType(TypeOfAny.special_form)

    def visit_list_expr(self, e: ListExpr) -> Type:
        """Type check a list expression [...]."""
        return self.check_lst_expr(e.items, 'builtins.list', '<list>', e)

    def visit_set_expr(self, e: SetExpr) -> Type:
        return self.check_lst_expr(e.items, 'builtins.set', '<set>', e)

    def check_lst_expr(self, items: List[Expression], fullname: str,
                       tag: str, context: Context) -> Type:
        # Translate into type checking a generic function call.
        # Used for list and set expressions, as well as for tuples
        # containing star expressions that don't refer to a
        # Tuple. (Note: "lst" stands for list-set-tuple. :-)
        tvdef = TypeVarDef('T', 'T', -1, [], self.object_type())
        tv = TypeVarType(tvdef)
        constructor = CallableType(
            [tv],
            [nodes.ARG_STAR],
            [None],
            self.chk.named_generic_type(fullname, [tv]),
            self.named_type('builtins.function'),
            name=tag,
            variables=[tvdef])
        return self.check_call(constructor,
                               [(i.expr if isinstance(i, StarExpr) else i)
                                for i in items],
                               [(nodes.ARG_STAR if isinstance(i, StarExpr) else nodes.ARG_POS)
                                for i in items],
                               context)[0]

    def visit_tuple_expr(self, e: TupleExpr) -> Type:
        """Type check a tuple expression."""
        # Try to determine type context for type inference.
        type_context = self.type_context[-1]
        type_context_items = None
        if isinstance(type_context, UnionType):
            tuples_in_context = [t for t in type_context.items
                                 if (isinstance(t, TupleType) and len(t.items) == len(e.items)) or
                                 is_named_instance(t, 'builtins.tuple')]
            if len(tuples_in_context) == 1:
                type_context = tuples_in_context[0]
            else:
                # There are either no relevant tuples in the Union, or there is
                # more than one.  Either way, we can't decide on a context.
                pass

        if isinstance(type_context, TupleType):
            type_context_items = type_context.items
        elif type_context and is_named_instance(type_context, 'builtins.tuple'):
            assert isinstance(type_context, Instance)
            if type_context.args:
                type_context_items = [type_context.args[0]] * len(e.items)
        # NOTE: it's possible for the context to have a different
        # number of items than e.  In that case we use those context
        # items that match a position in e, and we'll worry about type
        # mismatches later.

        # Infer item types.  Give up if there's a star expression
        # that's not a Tuple.
        items = []  # type: List[Type]
        j = 0  # Index into type_context_items; irrelevant if type_context_items is none
        for i in range(len(e.items)):
            item = e.items[i]
            if isinstance(item, StarExpr):
                # Special handling for star expressions.
                # TODO: If there's a context, and item.expr is a
                # TupleExpr, flatten it, so we can benefit from the
                # context?  Counterargument: Why would anyone write
                # (1, *(2, 3)) instead of (1, 2, 3) except in a test?
                tt = self.accept(item.expr)
                if isinstance(tt, TupleType):
                    items.extend(tt.items)
                    j += len(tt.items)
                else:
                    # A star expression that's not a Tuple.
                    # Treat the whole thing as a variable-length tuple.
                    return self.check_lst_expr(e.items, 'builtins.tuple', '<tuple>', e)
            else:
                if not type_context_items or j >= len(type_context_items):
                    tt = self.accept(item)
                else:
                    tt = self.accept(item, type_context_items[j])
                    j += 1
                items.append(tt)
        fallback_item = join.join_type_list(items)
        return TupleType(items, self.chk.named_generic_type('builtins.tuple', [fallback_item]))

    def visit_dict_expr(self, e: DictExpr) -> Type:
        """Type check a dict expression.

        Translate it into a call to dict(), with provisions for **expr.
        """
        # if the dict literal doesn't match TypedDict, check_typeddict_call_with_dict reports
        # an error, but returns the TypedDict type that matches the literal it found
        # that would cause a second error when that TypedDict type is returned upstream
        # to avoid the second error, we always return TypedDict type that was requested
        typeddict_context = self.find_typeddict_context(self.type_context[-1])
        if typeddict_context:
            self.check_typeddict_call_with_dict(
                callee=typeddict_context,
                kwargs=e,
                context=e
            )
            return typeddict_context.copy_modified()

        # Collect function arguments, watching out for **expr.
        args = []  # type: List[Expression]  # Regular "key: value"
        stargs = []  # type: List[Expression]  # For "**expr"
        for key, value in e.items:
            if key is None:
                stargs.append(value)
            else:
                args.append(TupleExpr([key, value]))
        # Define type variables (used in constructors below).
        ktdef = TypeVarDef('KT', 'KT', -1, [], self.object_type())
        vtdef = TypeVarDef('VT', 'VT', -2, [], self.object_type())
        kt = TypeVarType(ktdef)
        vt = TypeVarType(vtdef)
        rv = None
        # Call dict(*args), unless it's empty and stargs is not.
        if args or not stargs:
            # The callable type represents a function like this:
            #
            #   def <unnamed>(*v: Tuple[kt, vt]) -> Dict[kt, vt]: ...
            constructor = CallableType(
                [TupleType([kt, vt], self.named_type('builtins.tuple'))],
                [nodes.ARG_STAR],
                [None],
                self.chk.named_generic_type('builtins.dict', [kt, vt]),
                self.named_type('builtins.function'),
                name='<dict>',
                variables=[ktdef, vtdef])
            rv = self.check_call(constructor, args, [nodes.ARG_POS] * len(args), e)[0]
        else:
            # dict(...) will be called below.
            pass
        # Call rv.update(arg) for each arg in **stargs,
        # except if rv isn't set yet, then set rv = dict(arg).
        if stargs:
            for arg in stargs:
                if rv is None:
                    constructor = CallableType(
                        [self.chk.named_generic_type('typing.Mapping', [kt, vt])],
                        [nodes.ARG_POS],
                        [None],
                        self.chk.named_generic_type('builtins.dict', [kt, vt]),
                        self.named_type('builtins.function'),
                        name='<list>',
                        variables=[ktdef, vtdef])
                    rv = self.check_call(constructor, [arg], [nodes.ARG_POS], arg)[0]
                else:
                    method = self.analyze_external_member_access('update', rv, arg)
                    self.check_call(method, [arg], [nodes.ARG_POS], arg)
        assert rv is not None
        return rv

    def find_typeddict_context(self, context: Optional[Type]) -> Optional[TypedDictType]:
        if isinstance(context, TypedDictType):
            return context
        elif isinstance(context, UnionType):
            items = []
            for item in context.items:
                item_context = self.find_typeddict_context(item)
                if item_context:
                    items.append(item_context)
            if len(items) == 1:
                # Only one union item is TypedDict, so use the context as it's unambiguous.
                return items[0]
        # No TypedDict type in context.
        return None

    def visit_lambda_expr(self, e: LambdaExpr) -> Type:
        """Type check lambda expression."""
        inferred_type, type_override = self.infer_lambda_type_using_context(e)
        if not inferred_type:
            self.chk.return_types.append(AnyType(TypeOfAny.special_form))
            # No useful type context.
            ret_type = self.accept(e.expr(), allow_none_return=True)
            fallback = self.named_type('builtins.function')
            self.chk.return_types.pop()
            return callable_type(e, fallback, ret_type)
        else:
            # Type context available.
            self.chk.return_types.append(inferred_type.ret_type)
            self.chk.check_func_item(e, type_override=type_override)
            if e.expr() not in self.chk.type_map:
                self.accept(e.expr(), allow_none_return=True)
            ret_type = self.chk.type_map[e.expr()]
            if isinstance(ret_type, NoneTyp):
                # For "lambda ...: None", just use type from the context.
                # Important when the context is Callable[..., None] which
                # really means Void. See #1425.
                self.chk.return_types.pop()
                return inferred_type
            self.chk.return_types.pop()
            return replace_callable_return_type(inferred_type, ret_type)

    def infer_lambda_type_using_context(self, e: LambdaExpr) -> Tuple[Optional[CallableType],
                                                                    Optional[CallableType]]:
        """Try to infer lambda expression type using context.

        Return None if could not infer type.
        The second item in the return type is the type_override parameter for check_func_item.
        """
        # TODO also accept 'Any' context
        ctx = self.type_context[-1]

        if isinstance(ctx, UnionType):
            callables = [t for t in ctx.relevant_items() if isinstance(t, CallableType)]
            if len(callables) == 1:
                ctx = callables[0]

        if not ctx or not isinstance(ctx, CallableType):
            return None, None

        # The context may have function type variables in it. We replace them
        # since these are the type variables we are ultimately trying to infer;
        # they must be considered as indeterminate. We use ErasedType since it
        # does not affect type inference results (it is for purposes like this
        # only).
        callable_ctx = replace_meta_vars(ctx, ErasedType())
        assert isinstance(callable_ctx, CallableType)

        arg_kinds = [arg.kind for arg in e.arguments]

        if callable_ctx.is_ellipsis_args:
            # Fill in Any arguments to match the arguments of the lambda.
            callable_ctx = callable_ctx.copy_modified(
                is_ellipsis_args=False,
                arg_types=[AnyType(TypeOfAny.special_form)] * len(arg_kinds),
                arg_kinds=arg_kinds,
                arg_names=[None] * len(arg_kinds)
            )

        if ARG_STAR in arg_kinds or ARG_STAR2 in arg_kinds:
            # TODO treat this case appropriately
            return callable_ctx, None
        if callable_ctx.arg_kinds != arg_kinds:
            # Incompatible context; cannot use it to infer types.
            self.chk.fail(messages.CANNOT_INFER_LAMBDA_TYPE, e)
            return None, None

        return callable_ctx, callable_ctx

    def visit_super_expr(self, e: SuperExpr) -> Type:
        """Type check a super expression (non-lvalue)."""
        self.check_super_arguments(e)
        t = self.analyze_super(e, False)
        return t

    def check_super_arguments(self, e: SuperExpr) -> None:
        """Check arguments in a super(...) call."""
        if ARG_STAR in e.call.arg_kinds:
            self.chk.fail('Varargs not supported with "super"', e)
        elif e.call.args and set(e.call.arg_kinds) != {ARG_POS}:
            self.chk.fail('"super" only accepts positional arguments', e)
        elif len(e.call.args) == 1:
            self.chk.fail('"super" with a single argument not supported', e)
        elif len(e.call.args) > 2:
            self.chk.fail('Too many arguments for "super"', e)
        elif self.chk.options.python_version[0] == 2 and len(e.call.args) == 0:
            self.chk.fail('Too few arguments for "super"', e)
        elif len(e.call.args) == 2:
            type_obj_type = self.accept(e.call.args[0])
            instance_type = self.accept(e.call.args[1])
            if isinstance(type_obj_type, FunctionLike) and type_obj_type.is_type_obj():
                type_info = type_obj_type.type_object()
            elif isinstance(type_obj_type, TypeType):
                item = type_obj_type.item
                if isinstance(item, AnyType):
                    # Could be anything.
                    return
                if isinstance(item, TupleType):
                    item = item.fallback  # Handle named tuples and other Tuple[...] subclasses.
                if not isinstance(item, Instance):
                    # A complicated type object type. Too tricky, give up.
                    # TODO: Do something more clever here.
                    self.chk.fail('Unsupported argument 1 for "super"', e)
                    return
                type_info = item.type
            elif isinstance(type_obj_type, AnyType):
                return
            else:
                self.msg.first_argument_for_super_must_be_type(type_obj_type, e)
                return

            if isinstance(instance_type, (Instance, TupleType, TypeVarType)):
                if isinstance(instance_type, TypeVarType):
                    # Needed for generic self.
                    instance_type = instance_type.upper_bound
                    if not isinstance(instance_type, (Instance, TupleType)):
                        # Too tricky, give up.
                        # TODO: Do something more clever here.
                        self.chk.fail(messages.UNSUPPORTED_ARGUMENT_2_FOR_SUPER, e)
                        return
                if isinstance(instance_type, TupleType):
                    # Needed for named tuples and other Tuple[...] subclasses.
                    instance_type = instance_type.fallback
                if type_info not in instance_type.type.mro:
                    self.chk.fail('Argument 2 for "super" not an instance of argument 1', e)
            elif isinstance(instance_type, TypeType) or (isinstance(instance_type, FunctionLike)
                                                         and instance_type.is_type_obj()):
                # TODO: Check whether this is a valid type object here.
                pass
            elif not isinstance(instance_type, AnyType):
                self.chk.fail(messages.UNSUPPORTED_ARGUMENT_2_FOR_SUPER, e)

    def analyze_super(self, e: SuperExpr, is_lvalue: bool) -> Type:
        """Type check a super expression."""
        if e.info and e.info.bases:
            # TODO fix multiple inheritance etc
            if len(e.info.mro) < 2:
                self.chk.fail('Internal error: unexpected mro for {}: {}'.format(
                    e.info.name(), e.info.mro), e)
                return AnyType(TypeOfAny.from_error)
            for base in e.info.mro[1:]:
                if e.name in base.names or base == e.info.mro[-1]:
                    if e.info.fallback_to_any and base == e.info.mro[-1]:
                        # There's an undefined base class, and we're
                        # at the end of the chain.  That's not an error.
                        return AnyType(TypeOfAny.special_form)
                    if not self.chk.in_checked_function():
                        return AnyType(TypeOfAny.unannotated)
                    if self.chk.scope.active_class() is not None:
                        self.chk.fail('super() outside of a method is not supported', e)
                        return AnyType(TypeOfAny.from_error)
                    method = self.chk.scope.top_function()
                    assert method is not None
                    args = method.arguments
                    # super() in a function with empty args is an error; we
                    # need something in declared_self.
                    if not args:
                        self.chk.fail(
                            'super() requires one or more positional arguments in '
                            'enclosing function', e)
                        return AnyType(TypeOfAny.from_error)
                    declared_self = args[0].variable.type or fill_typevars(e.info)
                    return analyze_member_access(name=e.name, typ=fill_typevars(e.info), node=e,
                                                 is_lvalue=False, is_super=True, is_operator=False,
                                                 builtin_type=self.named_type,
                                                 not_ready_callback=self.not_ready_callback,
                                                 msg=self.msg, override_info=base,
                                                 original_type=declared_self, chk=self.chk)
            assert False, 'unreachable'
        else:
            # Invalid super. This has been reported by the semantic analyzer.
            return AnyType(TypeOfAny.from_error)

    def visit_slice_expr(self, e: SliceExpr) -> Type:
        expected = make_optional_type(self.named_type('builtins.int'))
        for index in [e.begin_index, e.end_index, e.stride]:
            if index:
                t = self.accept(index)
                self.chk.check_subtype(t, expected,
                                       index, messages.INVALID_SLICE_INDEX)
        return self.named_type('builtins.slice')

    def visit_list_comprehension(self, e: ListComprehension) -> Type:
        return self.check_generator_or_comprehension(
            e.generator, 'builtins.list', '<list-comprehension>')

    def visit_set_comprehension(self, e: SetComprehension) -> Type:
        return self.check_generator_or_comprehension(
            e.generator, 'builtins.set', '<set-comprehension>')

    def visit_generator_expr(self, e: GeneratorExpr) -> Type:
        # If any of the comprehensions use async for, the expression will return an async generator
        # object
        if any(e.is_async):
            typ = 'typing.AsyncGenerator'
            # received type is always None in async generator expressions
            additional_args = [NoneTyp()]  # type: List[Type]
        else:
            typ = 'typing.Generator'
            # received type and returned type are None
            additional_args = [NoneTyp(), NoneTyp()]
        return self.check_generator_or_comprehension(e, typ, '<generator>',
                                                     additional_args=additional_args)

    def check_generator_or_comprehension(self, gen: GeneratorExpr,
                                         type_name: str,
                                         id_for_messages: str,
                                         additional_args: List[Type] = []) -> Type:
        """Type check a generator expression or a list comprehension."""
        with self.chk.binder.frame_context(can_skip=True, fall_through=0):
            self.check_for_comp(gen)

            # Infer the type of the list comprehension by using a synthetic generic
            # callable type.
            tvdef = TypeVarDef('T', 'T', -1, [], self.object_type())
            tv_list = [TypeVarType(tvdef)]  # type: List[Type]
            constructor = CallableType(
                tv_list,
                [nodes.ARG_POS],
                [None],
                self.chk.named_generic_type(type_name, tv_list + additional_args),
                self.chk.named_type('builtins.function'),
                name=id_for_messages,
                variables=[tvdef])
            return self.check_call(constructor,
                                [gen.left_expr], [nodes.ARG_POS], gen)[0]

    def visit_dictionary_comprehension(self, e: DictionaryComprehension) -> Type:
        """Type check a dictionary comprehension."""
        with self.chk.binder.frame_context(can_skip=True, fall_through=0):
            self.check_for_comp(e)

            # Infer the type of the list comprehension by using a synthetic generic
            # callable type.
            ktdef = TypeVarDef('KT', 'KT', -1, [], self.object_type())
            vtdef = TypeVarDef('VT', 'VT', -2, [], self.object_type())
            kt = TypeVarType(ktdef)
            vt = TypeVarType(vtdef)
            constructor = CallableType(
                [kt, vt],
                [nodes.ARG_POS, nodes.ARG_POS],
                [None, None],
                self.chk.named_generic_type('builtins.dict', [kt, vt]),
                self.chk.named_type('builtins.function'),
                name='<dictionary-comprehension>',
                variables=[ktdef, vtdef])
            return self.check_call(constructor,
                                   [e.key, e.value], [nodes.ARG_POS, nodes.ARG_POS], e)[0]

    def check_for_comp(self, e: Union[GeneratorExpr, DictionaryComprehension]) -> None:
        """Check the for_comp part of comprehensions. That is the part from 'for':
        ... for x in y if z

        Note: This adds the type information derived from the condlists to the current binder.
        """
        for index, sequence, conditions, is_async in zip(e.indices, e.sequences,
                                                         e.condlists, e.is_async):
            if is_async:
                _, sequence_type = self.chk.analyze_async_iterable_item_type(sequence)
            else:
                _, sequence_type = self.chk.analyze_iterable_item_type(sequence)
            self.chk.analyze_index_variables(index, sequence_type, True, e)
            for condition in conditions:
                self.accept(condition)

                # values are only part of the comprehension when all conditions are true
                true_map, _ = self.chk.find_isinstance_check(condition)

                if true_map:
                    for var, type in true_map.items():
                        self.chk.binder.put(var, type)

    def visit_conditional_expr(self, e: ConditionalExpr) -> Type:
        self.accept(e.cond)
        ctx = self.type_context[-1]

        # Gain type information from isinstance if it is there
        # but only for the current expression
        if_map, else_map = self.chk.find_isinstance_check(e.cond)

        if_type = self.analyze_cond_branch(if_map, e.if_expr, context=ctx)

        if not mypy.checker.is_valid_inferred_type(if_type):
            # Analyze the right branch disregarding the left branch.
            else_type = self.analyze_cond_branch(else_map, e.else_expr, context=ctx)

            # If it would make a difference, re-analyze the left
            # branch using the right branch's type as context.
            if ctx is None or not is_equivalent(else_type, ctx):
                # TODO: If it's possible that the previous analysis of
                # the left branch produced errors that are avoided
                # using this context, suppress those errors.
                if_type = self.analyze_cond_branch(if_map, e.if_expr, context=else_type)

        else:
            # Analyze the right branch in the context of the left
            # branch's type.
            else_type = self.analyze_cond_branch(else_map, e.else_expr, context=if_type)

        # Only create a union type if the type context is a union, to be mostly
        # compatible with older mypy versions where we always did a join.
        #
        # TODO: Always create a union or at least in more cases?
        if isinstance(self.type_context[-1], UnionType):
            res = UnionType.make_simplified_union([if_type, else_type])
        else:
            res = join.join_types(if_type, else_type)

        return res

    def analyze_cond_branch(self, map: Optional[Dict[Expression, Type]],
                            node: Expression, context: Optional[Type]) -> Type:
        with self.chk.binder.frame_context(can_skip=True, fall_through=0):
            if map is None:
                # We still need to type check node, in case we want to
                # process it for isinstance checks later
                self.accept(node, type_context=context)
                return UninhabitedType()
            self.chk.push_type_map(map)
            return self.accept(node, type_context=context)

    def visit_backquote_expr(self, e: BackquoteExpr) -> Type:
        self.accept(e.expr)
        return self.named_type('builtins.str')

    #
    # Helpers
    #

    def accept(self,
               node: Expression,
               type_context: Optional[Type] = None,
               allow_none_return: bool = False,
               always_allow_any: bool = False,
               ) -> Type:
        """Type check a node in the given type context.  If allow_none_return
        is True and this expression is a call, allow it to return None.  This
        applies only to this expression and not any subexpressions.
        """
        if node in self.type_overrides:
            return self.type_overrides[node]
        self.type_context.append(type_context)
        try:
            if allow_none_return and isinstance(node, CallExpr):
                typ = self.visit_call_expr(node, allow_none_return=True)
            elif allow_none_return and isinstance(node, YieldFromExpr):
                typ = self.visit_yield_from_expr(node, allow_none_return=True)
            else:
                typ = node.accept(self)
        except Exception as err:
            report_internal_error(err, self.chk.errors.file,
                                  node.line, self.chk.errors, self.chk.options)
        self.type_context.pop()
        assert typ is not None
        self.chk.store_type(node, typ)

        if (self.chk.options.disallow_any_expr and
                not always_allow_any and
                not self.chk.is_stub and
                self.chk.in_checked_function() and
                has_any_type(typ)):
            self.msg.disallowed_any_type(typ, node)

        if not self.chk.in_checked_function():
            return AnyType(TypeOfAny.unannotated)
        else:
            return typ

    def named_type(self, name: str) -> Instance:
        """Return an instance type with type given by the name and no type
        arguments. Alias for TypeChecker.named_type.
        """
        return self.chk.named_type(name)

    def is_valid_var_arg(self, typ: Type) -> bool:
        """Is a type valid as a *args argument?"""
        return (isinstance(typ, TupleType) or
                is_subtype(typ, self.chk.named_generic_type('typing.Iterable',
                                                            [AnyType(TypeOfAny.special_form)])) or
                isinstance(typ, AnyType))

    def is_valid_keyword_var_arg(self, typ: Type) -> bool:
        """Is a type valid as a **kwargs argument?"""
        if self.chk.options.python_version[0] >= 3:
            return is_subtype(typ, self.chk.named_generic_type(
                'typing.Mapping', [self.named_type('builtins.str'),
                                   AnyType(TypeOfAny.special_form)]))
        else:
            return (
                is_subtype(typ, self.chk.named_generic_type(
                    'typing.Mapping',
                    [self.named_type('builtins.str'),
                     AnyType(TypeOfAny.special_form)]))
                or
                is_subtype(typ, self.chk.named_generic_type(
                    'typing.Mapping',
                    [self.named_type('builtins.unicode'),
                     AnyType(TypeOfAny.special_form)])))

    def has_member(self, typ: Type, member: str) -> bool:
        """Does type have member with the given name?"""
        # TODO: refactor this to use checkmember.analyze_member_access, otherwise
        # these two should be carefully kept in sync.
        if isinstance(typ, TypeVarType):
            typ = typ.upper_bound
        if isinstance(typ, TupleType):
            typ = typ.fallback
        if isinstance(typ, Instance):
            return typ.type.has_readable_member(member)
        if isinstance(typ, CallableType) and typ.is_type_obj():
            return typ.fallback.type.has_readable_member(member)
        elif isinstance(typ, AnyType):
            return True
        elif isinstance(typ, UnionType):
            result = all(self.has_member(x, member) for x in typ.relevant_items())
            return result
        elif isinstance(typ, TypeType):
            # Type[Union[X, ...]] is always normalized to Union[Type[X], ...],
            # so we don't need to care about unions here.
            item = typ.item
            if isinstance(item, TypeVarType):
                item = item.upper_bound
            if isinstance(item, TupleType):
                item = item.fallback
            if isinstance(item, Instance) and item.type.metaclass_type is not None:
                return self.has_member(item.type.metaclass_type, member)
            if isinstance(item, AnyType):
                return True
            return False
        else:
            return False

    def not_ready_callback(self, name: str, context: Context) -> None:
        """Called when we can't infer the type of a variable because it's not ready yet.

        Either defer type checking of the enclosing function to the next
        pass or report an error.
        """
        self.chk.handle_cannot_determine_type(name, context)

    def visit_yield_expr(self, e: YieldExpr) -> Type:
        return_type = self.chk.return_types[-1]
        expected_item_type = self.chk.get_generator_yield_type(return_type, False)
        if e.expr is None:
            if (not isinstance(expected_item_type, (NoneTyp, AnyType))
                    and self.chk.in_checked_function()):
                self.chk.fail(messages.YIELD_VALUE_EXPECTED, e)
        else:
            actual_item_type = self.accept(e.expr, expected_item_type)
            self.chk.check_subtype(actual_item_type, expected_item_type, e,
                                   messages.INCOMPATIBLE_TYPES_IN_YIELD,
                                   'actual type', 'expected type')
        return self.chk.get_generator_receive_type(return_type, False)

    def visit_await_expr(self, e: AwaitExpr) -> Type:
        expected_type = self.type_context[-1]
        if expected_type is not None:
            expected_type = self.chk.named_generic_type('typing.Awaitable', [expected_type])
        actual_type = self.accept(e.expr, expected_type)
        if isinstance(actual_type, AnyType):
            return AnyType(TypeOfAny.from_another_any, source_any=actual_type)
        return self.check_awaitable_expr(actual_type, e, messages.INCOMPATIBLE_TYPES_IN_AWAIT)

    def check_awaitable_expr(self, t: Type, ctx: Context, msg: str) -> Type:
        """Check the argument to `await` and extract the type of value.

        Also used by `async for` and `async with`.
        """
        if not self.chk.check_subtype(t, self.named_type('typing.Awaitable'), ctx,
                                      msg, 'actual type', 'expected type'):
            return AnyType(TypeOfAny.special_form)
        else:
            method = self.analyze_external_member_access('__await__', t, ctx)
            generator = self.check_call(method, [], [], ctx)[0]
            return self.chk.get_generator_return_type(generator, False)

    def visit_yield_from_expr(self, e: YieldFromExpr, allow_none_return: bool = False) -> Type:
        # NOTE: Whether `yield from` accepts an `async def` decorated
        # with `@types.coroutine` (or `@asyncio.coroutine`) depends on
        # whether the generator containing the `yield from` is itself
        # thus decorated.  But it accepts a generator regardless of
        # how it's decorated.
        return_type = self.chk.return_types[-1]
        # TODO: What should the context for the sub-expression be?
        # If the containing function has type Generator[X, Y, ...],
        # the context should be Generator[X, Y, T], where T is the
        # context of the 'yield from' itself (but it isn't known).
        subexpr_type = self.accept(e.expr)

        # Check that the expr is an instance of Iterable and get the type of the iterator produced
        # by __iter__.
        if isinstance(subexpr_type, AnyType):
            iter_type = AnyType(TypeOfAny.from_another_any, source_any=subexpr_type)  # type: Type
        elif self.chk.type_is_iterable(subexpr_type):
            if is_async_def(subexpr_type) and not has_coroutine_decorator(return_type):
                self.chk.msg.yield_from_invalid_operand_type(subexpr_type, e)
            iter_method_type = self.analyze_external_member_access(
                '__iter__',
                subexpr_type,
                AnyType(TypeOfAny.special_form))

            any_type = AnyType(TypeOfAny.special_form)
            generic_generator_type = self.chk.named_generic_type('typing.Generator',
                                                                 [any_type, any_type, any_type])
            iter_type, _ = self.check_call(iter_method_type, [], [],
                                           context=generic_generator_type)
        else:
            if not (is_async_def(subexpr_type) and has_coroutine_decorator(return_type)):
                self.chk.msg.yield_from_invalid_operand_type(subexpr_type, e)
                iter_type = AnyType(TypeOfAny.from_error)
            else:
                iter_type = self.check_awaitable_expr(subexpr_type, e,
                                                      messages.INCOMPATIBLE_TYPES_IN_YIELD_FROM)

        # Check that the iterator's item type matches the type yielded by the Generator function
        # containing this `yield from` expression.
        expected_item_type = self.chk.get_generator_yield_type(return_type, False)
        actual_item_type = self.chk.get_generator_yield_type(iter_type, False)

        self.chk.check_subtype(actual_item_type, expected_item_type, e,
                           messages.INCOMPATIBLE_TYPES_IN_YIELD_FROM,
                           'actual type', 'expected type')

        # Determine the type of the entire yield from expression.
        if (isinstance(iter_type, Instance) and
                iter_type.type.fullname() == 'typing.Generator'):
            expr_type = self.chk.get_generator_return_type(iter_type, False)
        else:
            # Non-Generators don't return anything from `yield from` expressions.
            # However special-case Any (which might be produced by an error).
            if isinstance(actual_item_type, AnyType):
                expr_type = AnyType(TypeOfAny.from_another_any, source_any=actual_item_type)
            else:
                # Treat `Iterator[X]` as a shorthand for `Generator[X, None, Any]`.
                expr_type = NoneTyp()

        if not allow_none_return and isinstance(expr_type, NoneTyp):
            self.chk.msg.does_not_return_value(None, e)
        return expr_type

    def visit_temp_node(self, e: TempNode) -> Type:
        return e.type

    def visit_type_var_expr(self, e: TypeVarExpr) -> Type:
        return AnyType(TypeOfAny.special_form)

    def visit_newtype_expr(self, e: NewTypeExpr) -> Type:
        return AnyType(TypeOfAny.special_form)

    def visit_namedtuple_expr(self, e: NamedTupleExpr) -> Type:
        tuple_type = e.info.tuple_type
        if tuple_type:
            if (self.chk.options.disallow_any_unimported and
                    has_any_from_unimported_type(tuple_type)):
                self.msg.unimported_type_becomes_any("NamedTuple type", tuple_type, e)
            check_for_explicit_any(tuple_type, self.chk.options, self.chk.is_typeshed_stub,
                                   self.msg, context=e)
        return AnyType(TypeOfAny.special_form)

    def visit_enum_call_expr(self, e: EnumCallExpr) -> Type:
        for name, value in zip(e.items, e.values):
            if value is not None:
                typ = self.accept(value)
                if not isinstance(typ, AnyType):
                    var = e.info.names[name].node
                    if isinstance(var, Var):
                        # Inline TypeChecker.set_inferred_type(),
                        # without the lvalue.  (This doesn't really do
                        # much, since the value attribute is defined
                        # to have type Any in the typeshed stub.)
                        var.type = typ
                        var.is_inferred = True
        return AnyType(TypeOfAny.special_form)

    def visit_typeddict_expr(self, e: TypedDictExpr) -> Type:
        return AnyType(TypeOfAny.special_form)

    def visit__promote_expr(self, e: PromoteExpr) -> Type:
        return e.type

    def visit_star_expr(self, e: StarExpr) -> StarType:
        return StarType(self.accept(e.expr))

    def object_type(self) -> Instance:
        """Return instance type 'object'."""
        return self.named_type('builtins.object')

    def bool_type(self) -> Instance:
        """Return instance type 'bool'."""
        return self.named_type('builtins.bool')

    def narrow_type_from_binder(self, expr: Expression, known_type: Type) -> Type:
        if literal(expr) >= LITERAL_TYPE:
            restriction = self.chk.binder.get(expr)
            # If the current node is deferred, some variables may get Any types that they
            # otherwise wouldn't have. We don't want to narrow down these since it may
            # produce invalid inferred Optional[Any] types, at least.
            if restriction and not (isinstance(known_type, AnyType)
                                    and self.chk.current_node_deferred):
                ans = narrow_declared_type(known_type, restriction)
                return ans
        return known_type


def has_any_type(t: Type) -> bool:
    """Whether t contains an Any type"""
    return t.accept(HasAnyType())


class HasAnyType(types.TypeQuery[bool]):
    def __init__(self) -> None:
        super().__init__(any)

    def visit_any(self, t: AnyType) -> bool:
        return t.type_of_any != TypeOfAny.special_form  # special forms are not real Any types


def has_coroutine_decorator(t: Type) -> bool:
    """Whether t came from a function decorated with `@coroutine`."""
    return isinstance(t, Instance) and t.type.fullname() == 'typing.AwaitableGenerator'


def is_async_def(t: Type) -> bool:
    """Whether t came from a function defined using `async def`."""
    # In check_func_def(), when we see a function decorated with
    # `@typing.coroutine` or `@async.coroutine`, we change the
    # return type to typing.AwaitableGenerator[...], so that its
    # type is compatible with either Generator or Awaitable.
    # But for the check here we need to know whether the original
    # function (before decoration) was an `async def`.  The
    # AwaitableGenerator type conveniently preserves the original
    # type as its 4th parameter (3rd when using 0-origin indexing
    # :-), so that we can recover that information here.
    # (We really need to see whether the original, undecorated
    # function was an `async def`, which is orthogonal to its
    # decorations.)
    if (isinstance(t, Instance)
            and t.type.fullname() == 'typing.AwaitableGenerator'
            and len(t.args) >= 4):
        t = t.args[3]
    return isinstance(t, Instance) and t.type.fullname() == 'typing.Coroutine'


def map_actuals_to_formals(caller_kinds: List[int],
                           caller_names: Optional[Sequence[Optional[str]]],
                           callee_kinds: List[int],
                           callee_names: Sequence[Optional[str]],
                           caller_arg_type: Callable[[int],
                                                     Type]) -> List[List[int]]:
    """Calculate mapping between actual (caller) args and formals.

    The result contains a list of caller argument indexes mapping to each
    callee argument index, indexed by callee index.

    The caller_arg_type argument should evaluate to the type of the actual
    argument type with the given index.
    """
    ncallee = len(callee_kinds)
    map = [[] for i in range(ncallee)]  # type: List[List[int]]
    j = 0
    for i, kind in enumerate(caller_kinds):
        if kind == nodes.ARG_POS:
            if j < ncallee:
                if callee_kinds[j] in [nodes.ARG_POS, nodes.ARG_OPT,
                                       nodes.ARG_NAMED, nodes.ARG_NAMED_OPT]:
                    map[j].append(i)
                    j += 1
                elif callee_kinds[j] == nodes.ARG_STAR:
                    map[j].append(i)
        elif kind == nodes.ARG_STAR:
            # We need to know the actual type to map varargs.
            argt = caller_arg_type(i)
            if isinstance(argt, TupleType):
                # A tuple actual maps to a fixed number of formals.
                for _ in range(len(argt.items)):
                    if j < ncallee:
                        if callee_kinds[j] != nodes.ARG_STAR2:
                            map[j].append(i)
                        else:
                            break
                        if callee_kinds[j] != nodes.ARG_STAR:
                            j += 1
            else:
                # Assume that it is an iterable (if it isn't, there will be
                # an error later).
                while j < ncallee:
                    if callee_kinds[j] in (nodes.ARG_NAMED, nodes.ARG_NAMED_OPT, nodes.ARG_STAR2):
                        break
                    else:
                        map[j].append(i)
                    if callee_kinds[j] == nodes.ARG_STAR:
                        break
                    j += 1
        elif kind in (nodes.ARG_NAMED, nodes.ARG_NAMED_OPT):
            assert caller_names is not None, "Internal error: named kinds without names given"
            name = caller_names[i]
            if name in callee_names:
                map[callee_names.index(name)].append(i)
            elif nodes.ARG_STAR2 in callee_kinds:
                map[callee_kinds.index(nodes.ARG_STAR2)].append(i)
        else:
            assert kind == nodes.ARG_STAR2
            for j in range(ncallee):
                # TODO tuple varargs complicate this
                no_certain_match = (
                    not map[j] or caller_kinds[map[j][0]] == nodes.ARG_STAR)
                if ((callee_names[j] and no_certain_match)
                        or callee_kinds[j] == nodes.ARG_STAR2):
                    map[j].append(i)
    return map


def is_empty_tuple(t: Type) -> bool:
    return isinstance(t, TupleType) and not t.items


def is_duplicate_mapping(mapping: List[int], actual_kinds: List[int]) -> bool:
    # Multiple actuals can map to the same formal only if they both come from
    # varargs (*args and **kwargs); in this case at runtime it is possible that
    # there are no duplicates. We need to allow this, as the convention
    # f(..., *args, **kwargs) is common enough.
    return len(mapping) > 1 and not (
        len(mapping) == 2 and
        actual_kinds[mapping[0]] == nodes.ARG_STAR and
        actual_kinds[mapping[1]] == nodes.ARG_STAR2)


def replace_callable_return_type(c: CallableType, new_ret_type: Type) -> CallableType:
    """Return a copy of a callable type with a different return type."""
    return c.copy_modified(ret_type=new_ret_type)


class ArgInferSecondPassQuery(types.TypeQuery[bool]):
    """Query whether an argument type should be inferred in the second pass.

    The result is True if the type has a type variable in a callable return
    type anywhere. For example, the result for Callable[[], T] is True if t is
    a type variable.
    """
    def __init__(self) -> None:
        super().__init__(any)

    def visit_callable_type(self, t: CallableType) -> bool:
        return self.query_types(t.arg_types) or t.accept(HasTypeVarQuery())


class HasTypeVarQuery(types.TypeQuery[bool]):
    """Visitor for querying whether a type has a type variable component."""
    def __init__(self) -> None:
        super().__init__(any)

    def visit_type_var(self, t: TypeVarType) -> bool:
        return True


def has_erased_component(t: Optional[Type]) -> bool:
    return t is not None and t.accept(HasErasedComponentsQuery())


class HasErasedComponentsQuery(types.TypeQuery[bool]):
    """Visitor for querying whether a type has an erased component."""
    def __init__(self) -> None:
        super().__init__(any)

    def visit_erased_type(self, t: ErasedType) -> bool:
        return True


def has_uninhabited_component(t: Optional[Type]) -> bool:
    return t is not None and t.accept(HasUninhabitedComponentsQuery())


class HasUninhabitedComponentsQuery(types.TypeQuery[bool]):
    """Visitor for querying whether a type has an UninhabitedType component."""
    def __init__(self) -> None:
        super().__init__(any)

    def visit_uninhabited_type(self, t: UninhabitedType) -> bool:
        return True


def arg_approximate_similarity(actual: Type, formal: Type) -> bool:
    """Return if caller argument (actual) is roughly compatible with signature arg (formal).

    This function is deliberately loose and will report two types are similar
    as long as their "shapes" are plausibly the same.

    This is useful when we're doing error reporting: for example, if we're trying
    to select an overload alternative and there's no exact match, we can use
    this function to help us identify which alternative the user might have
    *meant* to match.
    """

    # Erase typevars: we'll consider them all to have the same "shape".

    if isinstance(actual, TypeVarType):
        actual = actual.erase_to_union_or_bound()
    if isinstance(formal, TypeVarType):
        formal = formal.erase_to_union_or_bound()

    # Callable or Type[...]-ish types

    def is_typetype_like(typ: Type) -> bool:
        return (isinstance(typ, TypeType)
                or (isinstance(typ, FunctionLike) and typ.is_type_obj())
                or (isinstance(typ, Instance) and typ.type.fullname() == "builtins.type"))

    if isinstance(formal, CallableType):
        if isinstance(actual, (CallableType, Overloaded, TypeType)):
            return True
    if is_typetype_like(actual) and is_typetype_like(formal):
        return True

    # Unions

    if isinstance(actual, UnionType):
        return any(arg_approximate_similarity(item, formal) for item in actual.relevant_items())
    if isinstance(formal, UnionType):
        return any(arg_approximate_similarity(actual, item) for item in formal.relevant_items())

    # TypedDicts

    if isinstance(actual, TypedDictType):
        if isinstance(formal, TypedDictType):
            return True
        return arg_approximate_similarity(actual.fallback, formal)

    # Instances
    # For instances, we mostly defer to the existing is_subtype check.

    if isinstance(formal, Instance):
        if isinstance(actual, CallableType):
            actual = actual.fallback
        if isinstance(actual, Overloaded):
            actual = actual.items()[0].fallback
        if isinstance(actual, TupleType):
            actual = actual.fallback
        if isinstance(actual, Instance) and formal.type in actual.type.mro:
            # Try performing a quick check as an optimization
            return True

    # Fall back to a standard subtype check for the remaining kinds of type.
    return is_subtype(erasetype.erase_type(actual), erasetype.erase_type(formal))


def any_causes_overload_ambiguity(items: List[CallableType],
                                  return_types: List[Type],
                                  arg_types: List[Type],
                                  arg_kinds: List[int],
                                  arg_names: Optional[Sequence[Optional[str]]]) -> bool:
    """May an argument containing 'Any' cause ambiguous result type on call to overloaded function?

    Note that this sometimes returns True even if there is no ambiguity, since a correct
    implementation would be complex (and the call would be imprecisely typed due to Any
    types anyway).

    Args:
        items: Overload items matching the actual arguments
        arg_types: Actual argument types
        arg_kinds: Actual argument kinds
        arg_names: Actual argument names
    """
    if all_same_types(return_types):
        return False

    actual_to_formal = [
        map_formals_to_actuals(
            arg_kinds, arg_names, item.arg_kinds, item.arg_names, lambda i: arg_types[i])
        for item in items
    ]

    for arg_idx, arg_type in enumerate(arg_types):
        if has_any_type(arg_type):
            matching_formals_unfiltered = [(item_idx, lookup[arg_idx])
                                           for item_idx, lookup in enumerate(actual_to_formal)
                                           if lookup[arg_idx]]

            matching_returns = []
            matching_formals = []
            for item_idx, formals in matching_formals_unfiltered:
                matched_callable = items[item_idx]
                matching_returns.append(matched_callable.ret_type)

                # Note: if an actual maps to multiple formals of differing types within
                # a single callable, then we know at least one of those formals must be
                # a different type then the formal(s) in some other callable.
                # So it's safe to just append everything to the same list.
                for formal in formals:
                    matching_formals.append(matched_callable.arg_types[formal])
            if not all_same_types(matching_formals) and not all_same_types(matching_returns):
                # Any maps to multiple different types, and the return types of these items differ.
                return True
    return False


def all_same_types(types: Iterable[Type]) -> bool:
    types = list(types)
    if len(types) == 0:
        return True
    return all(is_same_type(t, types[0]) for t in types[1:])


def map_formals_to_actuals(caller_kinds: List[int],
                           caller_names: Optional[Sequence[Optional[str]]],
                           callee_kinds: List[int],
                           callee_names: List[Optional[str]],
                           caller_arg_type: Callable[[int],
                                                     Type]) -> List[List[int]]:
    """Calculate the reverse mapping of map_actuals_to_formals."""
    formal_to_actual = map_actuals_to_formals(caller_kinds,
                                              caller_names,
                                              callee_kinds,
                                              callee_names,
                                              caller_arg_type)
    # Now reverse the mapping.
    actual_to_formal = [[] for _ in caller_kinds]  # type: List[List[int]]
    for formal, actuals in enumerate(formal_to_actual):
        for actual in actuals:
            actual_to_formal[actual].append(formal)
    return actual_to_formal


def merge_typevars_in_callables_by_name(
        callables: Sequence[CallableType]) -> Tuple[List[CallableType], List[TypeVarDef]]:
    """Takes all the typevars present in the callables and 'combines' the ones with the same name.

    For example, suppose we have two callables with signatures "f(x: T, y: S) -> T" and
    "f(x: List[Tuple[T, S]]) -> Tuple[T, S]". Both callables use typevars named "T" and
    "S", but we treat them as distinct, unrelated typevars. (E.g. they could both have
    distinct ids.)

    If we pass in both callables into this function, it returns a a list containing two
    new callables that are identical in signature, but use the same underlying TypeVarDef
    and TypeVarType objects for T and S.

    This is useful if we want to take the output lists and "merge" them into one callable
    in some way -- for example, when unioning together overloads.

    Returns both the new list of callables and a list of all distinct TypeVarDef objects used.
    """

    output = []  # type: List[CallableType]
    unique_typevars = {}  # type: Dict[str, TypeVarType]
    variables = []  # type: List[TypeVarDef]

    for target in callables:
        if target.is_generic():
            target = freshen_function_type_vars(target)

            rename = {}  # Dict[TypeVarId, TypeVar]
            for tvdef in target.variables:
                name = tvdef.fullname
                if name not in unique_typevars:
                    unique_typevars[name] = TypeVarType(tvdef)
                    variables.append(tvdef)
                rename[tvdef.id] = unique_typevars[name]

            target = cast(CallableType, expand_type(target, rename))
        output.append(target)

    return output, variables
