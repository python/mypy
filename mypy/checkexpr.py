"""Expression type checker. This file is conceptually part of TypeChecker."""

from collections import OrderedDict
from typing import cast, Dict, Set, List, Tuple, Callable, Union, Optional, Iterable, Sequence, Any

from mypy.errors import report_internal_error
from mypy.typeanal import has_any_from_unimported_type, check_for_explicit_any, set_any_tvars
from mypy.types import (
    Type, AnyType, CallableType, Overloaded, NoneTyp, TypeVarDef,
    TupleType, TypedDictType, Instance, TypeVarType, ErasedType, UnionType,
    PartialType, DeletedType, UnboundType, UninhabitedType, TypeType, TypeOfAny,
    true_only, false_only, is_named_instance, function_type, callable_type, FunctionLike,
    get_typ_args, set_typ_args,
    StarType)
from mypy.nodes import (
    NameExpr, RefExpr, Var, FuncDef, OverloadedFuncDef, TypeInfo, CallExpr,
    MemberExpr, IntExpr, StrExpr, BytesExpr, UnicodeExpr, FloatExpr,
    OpExpr, UnaryExpr, IndexExpr, CastExpr, RevealTypeExpr, TypeApplication, ListExpr,
    TupleExpr, DictExpr, LambdaExpr, SuperExpr, SliceExpr, Context, Expression,
    ListComprehension, GeneratorExpr, SetExpr, MypyFile, Decorator,
    ConditionalExpr, ComparisonExpr, TempNode, SetComprehension,
    DictionaryComprehension, ComplexExpr, EllipsisExpr, StarExpr, AwaitExpr, YieldExpr,
    YieldFromExpr, TypedDictExpr, PromoteExpr, NewTypeExpr, NamedTupleExpr, TypeVarExpr,
    TypeAliasExpr, BackquoteExpr, EnumCallExpr,
    ARG_POS, ARG_NAMED, ARG_STAR, ARG_STAR2, MODULE_REF, TVAR, LITERAL_TYPE,
)
from mypy.literals import literal
from mypy import nodes
import mypy.checker
from mypy import types
from mypy.sametypes import is_same_type
from mypy.erasetype import replace_meta_vars
from mypy.messages import MessageBuilder
from mypy import messages
from mypy.infer import infer_type_arguments, infer_function_type_arguments
from mypy import join
from mypy.meet import narrow_declared_type
from mypy.maptype import map_instance_to_supertype
from mypy.subtypes import is_subtype, is_equivalent, find_member, non_method_protocol_members
from mypy import applytype
from mypy import erasetype
from mypy.checkmember import analyze_member_access, type_object_type, bind_self
from mypy.constraints import get_actual_type
from mypy.checkstrformat import StringFormatterChecker
from mypy.expandtype import expand_type_by_instance, freshen_function_type_vars
from mypy.util import split_module_names
from mypy.typevars import fill_typevars
from mypy.visitor import ExpressionVisitor
from mypy.plugin import Plugin, MethodContext, MethodSigContext, FunctionContext
from mypy.typeanal import make_optional_type

from mypy import experiments

# Type of callback user for checking individual function arguments. See
# check_args() below for details.
ArgChecker = Callable[[Type, Type, int, Type, int, int, CallableType, Context, MessageBuilder],
                      None]


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
                if result.type is None:
                    # 'None' partial type. It has a well-defined type. In an lvalue context
                    # we want to preserve the knowledge of it being a partial type.
                    if not lvalue:
                        result = NoneTyp()
                else:
                    partial_types = self.chk.find_partial_types(node)
                    if partial_types is not None and not self.chk.current_node_deferred:
                        context = partial_types[node]
                        self.msg.fail(messages.NEED_ANNOTATION_FOR_VAR, context)
                    result = AnyType(TypeOfAny.special_form)
        elif isinstance(node, FuncDef):
            # Reference to a global function.
            result = function_type(node, self.named_type('builtins.function'))
        elif isinstance(node, OverloadedFuncDef) and node.type is not None:
            # node.type is None when there are multiple definitions of a function
            # and it's decorated by somthing that is not typing.overload
            result = node.type
        elif isinstance(node, TypeInfo):
            # Reference to a type object.
            result = type_object_type(node, self.named_type)
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
            # It's really a special form that only looks like a call.
            return self.accept(e.analyzed, self.type_context[-1])
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
                        # node.kind == TYPE_ALIAS only for aliases like It = Iterable[int].
                        or (isinstance(typ, NameExpr) and node and node.kind == nodes.TYPE_ALIAS)):
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
        if isinstance(ret_type, UninhabitedType):
            self.chk.binder.unreachable()
        if not allow_none_return and isinstance(ret_type, NoneTyp):
            self.chk.msg.does_not_return_value(callee_type, e)
            return AnyType(TypeOfAny.from_error)
        return ret_type

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
        item_name_exprs = [item[0] for item in kwargs.items]
        item_args = [item[1] for item in kwargs.items]

        item_names = []  # List[str]
        for item_name_expr in item_name_exprs:
            if not isinstance(item_name_expr, StrExpr):
                self.chk.fail(messages.TYPEDDICT_KEY_MUST_BE_STRING_LITERAL, item_name_expr)
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
                 }
    container_args = {'builtins.list': {'extend': ['builtins.list']},
                      'builtins.dict': {'update': ['builtins.dict']},
                      'builtins.set': {'update': ['builtins.set', 'builtins.list']},
                      }

    def try_infer_partial_type(self, e: CallExpr) -> None:
        if isinstance(e.callee, MemberExpr) and isinstance(e.callee.expr, RefExpr):
            var = cast(Var, e.callee.expr.node)
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
                or None if unavaiable (examples: 'builtins.open', 'typing.Mapping.get')
            object_type: If callable_name refers to a method, the type of the object
                on which the method is being called
        """
        arg_messages = arg_messages or self.msg
        if isinstance(callee, CallableType):
            if callable_name is None and callee.name:
                callable_name = callee.name
            if (isinstance(callable_node, RefExpr)
                and callable_node.fullname in ('enum.Enum', 'enum.IntEnum',
                                               'enum.Flag', 'enum.IntFlag')):
                # An Enum() call that failed SemanticAnalyzerPass2.check_enum_call().
                return callee.ret_type, callee

            if (callee.is_type_obj() and callee.type_object().is_abstract
                    # Exceptions for Type[...] and classmethod first argument
                    and not callee.from_type_type and not callee.is_classmethod_class):
                type = callee.type_object()
                self.msg.cannot_instantiate_abstract_class(
                    callee.type_object().name(), type.abstract_attributes,
                    context)
            elif (callee.is_type_obj() and callee.type_object().is_protocol
                  # Exceptions for Type[...] and classmethod first argument
                  and not callee.from_type_type and not callee.is_classmethod_class):
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

            arg_types = self.infer_arg_types_in_context2(
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
            # Type check arguments in empty context. They will be checked again
            # later in a context derived from the signature; these types are
            # only used to pick a signature variant.
            self.msg.disable_errors()
            arg_types = self.infer_arg_types_in_context(None, args)
            self.msg.enable_errors()

            target = self.overload_call_target(arg_types, arg_kinds, arg_names,
                                               callee, context,
                                               messages=arg_messages)
            return self.check_call(target, args, arg_kinds, context, arg_names,
                                   arg_messages=arg_messages,
                                   callable_name=callable_name,
                                   object_type=object_type)
        elif isinstance(callee, AnyType) or not self.chk.in_checked_function():
            self.infer_arg_types_in_context(None, args)
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
            return UnionType([self.analyze_type_type_callee(item, context)
                              for item in item.relevant_items()], item.line)
        if isinstance(item, TypeVarType):
            # Pretend we're calling the typevar's upper bound,
            # i.e. its constructor (a poor approximation for reality,
            # but better than AnyType...), but replace the return type
            # with typevar.
            callee = self.analyze_type_type_callee(item.upper_bound,
                                                   context)  # type: Optional[Type]
            if isinstance(callee, CallableType):
                if callee.is_generic():
                    callee = None
                else:
                    callee = callee.copy_modified(ret_type=item)
            elif isinstance(callee, Overloaded):
                if callee.items()[0].is_generic():
                    callee = None
                else:
                    callee = Overloaded([c.copy_modified(ret_type=item)
                                         for c in callee.items()])
            if callee:
                return callee

        self.msg.unsupported_type_type(item, context)
        return AnyType(TypeOfAny.from_error)

    def infer_arg_types_in_context(self, callee: Optional[CallableType],
                                   args: List[Expression]) -> List[Type]:
        """Infer argument expression types using a callable type as context.

        For example, if callee argument 2 has type List[int], infer the
        argument expression with List[int] type context.
        """
        # TODO Always called with callee as None, i.e. empty context.
        res = []  # type: List[Type]

        fixed = len(args)
        if callee:
            fixed = min(fixed, callee.max_fixed_args())

        ctx = None
        for i, arg in enumerate(args):
            if i < fixed:
                if callee and i < len(callee.arg_types):
                    ctx = callee.arg_types[i]
                arg_type = self.accept(arg, ctx)
            else:
                if callee and callee.is_var_arg:
                    arg_type = self.accept(arg, callee.arg_types[-1])
                else:
                    arg_type = self.accept(arg)
            if has_erased_component(arg_type):
                res.append(NoneTyp())
            else:
                res.append(arg_type)
        return res

    def infer_arg_types_in_context2(
            self, callee: CallableType, args: List[Expression], arg_kinds: List[int],
            formal_to_actual: List[List[int]]) -> List[Type]:
        """Infer argument expression types using a callable type as context.

        For example, if callee argument 2 has type List[int], infer the
        argument expression with List[int] type context.

        Returns the inferred types of *actual arguments*.
        """
        dummy = None  # type: Any
        res = [dummy] * len(args)  # type: List[Type]

        for i, actuals in enumerate(formal_to_actual):
            for ai in actuals:
                if arg_kinds[ai] not in (nodes.ARG_STAR, nodes.ARG_STAR2):
                    res[ai] = self.accept(args[ai], callee.arg_types[i])

        # Fill in the rest of the argument types.
        for i, t in enumerate(res):
            if not t:
                res[i] = self.accept(args[i])
        return res

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
        if isinstance(ret_type, TypeVarType):
            if ret_type.values or (not isinstance(ctx, Instance) or
                                   not ctx.args):
                # The return type is a type variable. If it has values, we can't easily restrict
                # type inference to conform to the valid values. If it's unrestricted, we could
                # infer a too general type for the type variable if we use context, and this could
                # result in confusing and spurious type errors elsewhere.
                #
                # Give up and just use function arguments for type inference. As an exception,
                # if the context is a generic instance type, actually use it as context, as
                # this *seems* to usually be the reasonable thing to do.
                #
                # See also github issues #462 and #360.
                ret_type = NoneTyp()
        args = infer_type_arguments(callable.type_var_ids(), ret_type, erased_ctx)
        # Only substitute non-Uninhabited and non-erased types.
        new_args = []  # type: List[Optional[Type]]
        for arg in args:
            if has_uninhabited_component(arg) or has_erased_component(arg):
                new_args.append(None)
            else:
                new_args.append(arg)
        return self.apply_generic_arguments(callable, new_args, error_context)

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

            arg_types = self.infer_arg_types_in_context2(
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

        arg_types = self.infer_arg_types_in_context2(
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
              (callee_type.item.type.is_abstract or callee_type.item.type.is_protocol) and
              # ...except for classmethod first argument
              not caller_type.is_classmethod_class):
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

    def overload_call_target(self, arg_types: List[Type], arg_kinds: List[int],
                             arg_names: Optional[Sequence[Optional[str]]],
                             overload: Overloaded, context: Context,
                             messages: Optional[MessageBuilder] = None) -> Type:
        """Infer the correct overload item to call with given argument types.

        The return value may be CallableType or AnyType (if an unique item
        could not be determined).
        """
        messages = messages or self.msg
        # TODO: For overlapping signatures we should try to get a more precise
        #       result than 'Any'.
        match = []  # type: List[CallableType]
        best_match = 0
        for typ in overload.items():
            similarity = self.erased_signature_similarity(arg_types, arg_kinds, arg_names,
                                                          typ, context=context)
            if similarity > 0 and similarity >= best_match:
                if (match and not is_same_type(match[-1].ret_type,
                                               typ.ret_type) and
                    (not mypy.checker.is_more_precise_signature(match[-1], typ)
                     or (any(isinstance(arg, AnyType) for arg in arg_types)
                         and any_arg_causes_overload_ambiguity(
                             match + [typ], arg_types, arg_kinds, arg_names)))):
                    # Ambiguous return type. Either the function overload is
                    # overlapping (which we don't handle very well here) or the
                    # caller has provided some Any argument types; in either
                    # case we'll fall back to Any. It's okay to use Any types
                    # in calls.
                    #
                    # Overlapping overload items are generally fine if the
                    # overlapping is only possible when there is multiple
                    # inheritance, as this is rare. See docstring of
                    # mypy.meet.is_overlapping_types for more about this.
                    #
                    # Note that there is no ambiguity if the items are
                    # covariant in both argument types and return types with
                    # respect to type precision. We'll pick the best/closest
                    # match.
                    #
                    # TODO: Consider returning a union type instead if the
                    #       overlapping is NOT due to Any types?
                    return AnyType(TypeOfAny.special_form)
                else:
                    match.append(typ)
                best_match = max(best_match, similarity)
        if not match:
            if not self.chk.should_suppress_optional_error(arg_types):
                messages.no_variant_matches_arguments(overload, arg_types, context)
            return AnyType(TypeOfAny.from_error)
        else:
            if len(match) == 1:
                return match[0]
            else:
                # More than one signature matches. Pick the first *non-erased*
                # matching signature, or default to the first one if none
                # match.
                for m in match:
                    if self.match_signature_types(arg_types, arg_kinds, arg_names, m,
                                                  context=context):
                        return m
                return match[0]

    def erased_signature_similarity(self, arg_types: List[Type], arg_kinds: List[int],
                                    arg_names: Optional[Sequence[Optional[str]]],
                                    callee: CallableType,
                                    context: Context) -> int:
        """Determine whether arguments could match the signature at runtime.

        Return similarity level (0 = no match, 1 = can match, 2 = non-promotion match). See
        overload_arg_similarity for a discussion of similarity levels.
        """
        formal_to_actual = map_actuals_to_formals(arg_kinds,
                                                  arg_names,
                                                  callee.arg_kinds,
                                                  callee.arg_names,
                                                  lambda i: arg_types[i])

        if not self.check_argument_count(callee, arg_types, arg_kinds, arg_names,
                                         formal_to_actual, None, None):
            # Too few or many arguments -> no match.
            return 0

        similarity = 2

        def check_arg(caller_type: Type, original_caller_type: Type, caller_kind: int,
                      callee_type: Type, n: int, m: int, callee: CallableType,
                      context: Context, messages: MessageBuilder) -> None:
            nonlocal similarity
            similarity = min(similarity,
                             overload_arg_similarity(caller_type, callee_type))
            if similarity == 0:
                # No match -- exit early since none of the remaining work can change
                # the result.
                raise Finished

        try:
            self.check_argument_types(arg_types, arg_kinds, callee, formal_to_actual,
                                      context=context, check_arg=check_arg)
        except Finished:
            pass

        return similarity

    def match_signature_types(self, arg_types: List[Type], arg_kinds: List[int],
                              arg_names: Optional[Sequence[Optional[str]]], callee: CallableType,
                              context: Context) -> bool:
        """Determine whether arguments types match the signature.

        Assume that argument counts are compatible.

        Return True if arguments match.
        """
        formal_to_actual = map_actuals_to_formals(arg_kinds,
                                                  arg_names,
                                                  callee.arg_kinds,
                                                  callee.arg_names,
                                                  lambda i: arg_types[i])
        ok = True

        def check_arg(caller_type: Type, original_caller_type: Type, caller_kind: int,
                      callee_type: Type, n: int, m: int, callee: CallableType,
                      context: Context, messages: MessageBuilder) -> None:
            nonlocal ok
            if not is_subtype(caller_type, callee_type):
                ok = False

        self.check_argument_types(arg_types, arg_kinds, callee, formal_to_actual,
                                  context=context, check_arg=check_arg)
        return ok

    def apply_generic_arguments(self, callable: CallableType, types: Sequence[Optional[Type]],
                                context: Context) -> CallableType:
        """Simple wrapper around mypy.applytype.apply_generic_arguments."""
        return applytype.apply_generic_arguments(callable, types, self.msg, context)

    def visit_member_expr(self, e: MemberExpr) -> Type:
        """Visit member expression (of form e.id)."""
        self.chk.module_refs.update(extract_refexpr_names(e))
        result = self.analyze_ordinary_member_access(e, False)
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
            if is_lvalue:
                return member_type
            else:
                return self.analyze_descriptor_access(original_type, member_type, e)

    def analyze_descriptor_access(self, instance_type: Type, descriptor_type: Type,
                                  context: Context) -> Type:
        """Type check descriptor access.

        Arguments:
            instance_type: The type of the instance on which the descriptor
                attribute is being accessed (the type of ``a`` in ``a.f`` when
                ``f`` is a descriptor).
            descriptor_type: The type of the descriptor attribute being accessed
                (the type of ``f`` in ``a.f`` when ``f`` is a descriptor).
            context: The node defining the context of this inference.
        Return:
            The return type of the appropriate ``__get__`` overload for the descriptor.
        """
        if not isinstance(descriptor_type, Instance):
            return descriptor_type

        if not descriptor_type.type.has_readable_member('__get__'):
            return descriptor_type

        dunder_get = descriptor_type.type.get_method('__get__')

        if dunder_get is None:
            self.msg.fail("{}.__get__ is not callable".format(descriptor_type), context)
            return AnyType(TypeOfAny.from_error)

        function = function_type(dunder_get, self.named_type('builtins.function'))
        bound_method = bind_self(function, descriptor_type)
        typ = map_instance_to_supertype(descriptor_type, dunder_get.info)
        dunder_get_type = expand_type_by_instance(bound_method, typ)

        if isinstance(instance_type, FunctionLike) and instance_type.is_type_obj():
            owner_type = instance_type.items()[0].ret_type
            instance_type = NoneTyp()
        elif isinstance(instance_type, TypeType):
            owner_type = instance_type.item
            instance_type = NoneTyp()
        else:
            owner_type = instance_type

        _, inferred_dunder_get_type = self.check_call(
            dunder_get_type,
            [TempNode(instance_type), TempNode(TypeType.make_normalized(owner_type))],
            [nodes.ARG_POS, nodes.ARG_POS], context)

        if isinstance(inferred_dunder_get_type, AnyType):
            # check_call failed, and will have reported an error
            return inferred_dunder_get_type

        if not isinstance(inferred_dunder_get_type, CallableType):
            self.msg.fail("{}.__get__ is not callable".format(descriptor_type), context)
            return AnyType(TypeOfAny.from_error)

        return inferred_dunder_get_type.ret_type

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
        result = None

        # Check each consecutive operand pair and their operator
        for left, right, operator in zip(e.operands, e.operands[1:], e.operators):
            left_type = self.accept(left)

            method_type = None  # type: Optional[mypy.types.Type]

            if operator == 'in' or operator == 'not in':
                right_type = self.accept(right)  # TODO only evaluate if needed

                # Keep track of whether we get type check errors (these won't be reported, they
                # are just to verify whether something is valid typing wise).
                local_errors = self.msg.copy()
                local_errors.disable_count = 0
                sub_result, method_type = self.check_op_local('__contains__', right_type,
                                                          left, e, local_errors)
                if isinstance(right_type, PartialType):
                    # We don't really know if this is an error or not, so just shut up.
                    pass
                elif (local_errors.is_errors() and
                    # is_valid_var_arg is True for any Iterable
                        self.is_valid_var_arg(right_type)):
                    itertype = self.chk.analyze_iterable_item_type(right)
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

    def _check_op_for_errors(self, method: str, base_type: Type, arg: Expression,
                             context: Context
                             ) -> Tuple[Tuple[Type, Type], MessageBuilder]:
        """Type check a binary operation which maps to a method call.

        Return ((result type, inferred operator method type), error message).
        """
        local_errors = self.msg.copy()
        local_errors.disable_count = 0
        result = self.check_op_local(method, base_type,
                                     arg, context,
                                     local_errors)
        return result, local_errors

    def check_op_local(self, method: str, base_type: Type, arg: Expression,
                       context: Context, local_errors: MessageBuilder) -> Tuple[Type, Type]:
        """Type check a binary operation which maps to a method call.

        Return tuple (result type, inferred operator method type).
        """
        method_type = analyze_member_access(method, base_type, context, False, False, True,
                                            self.named_type, self.not_ready_callback, local_errors,
                                            original_type=base_type, chk=self.chk)
        callable_name = None
        object_type = None
        if isinstance(base_type, Instance):
            # TODO: Find out in which class the method was defined originally?
            # TODO: Support non-Instance types.
            callable_name = '{}.{}'.format(base_type.type.fullname(), method)
            object_type = base_type
        return self.check_call(method_type, [arg], [nodes.ARG_POS],
                               context, arg_messages=local_errors,
                               callable_name=callable_name, object_type=object_type)

    def check_op(self, method: str, base_type: Type, arg: Expression,
                 context: Context,
                 allow_reverse: bool = False) -> Tuple[Type, Type]:
        """Type check a binary operation which maps to a method call.

        Return tuple (result type, inferred operator method type).
        """
        # Use a local error storage for errors related to invalid argument
        # type (but NOT other errors). This error may need to be suppressed
        # for operators which support __rX methods.
        local_errors = self.msg.copy()
        local_errors.disable_count = 0
        if not allow_reverse or self.has_member(base_type, method):
            result = self.check_op_local(method, base_type, arg, context,
                                         local_errors)
            if allow_reverse:
                arg_type = self.chk.type_map[arg]
                if isinstance(arg_type, AnyType):
                    # If the right operand has type Any, we can't make any
                    # conjectures about the type of the result, since the
                    # operand could have a __r method that returns anything.
                    any_type = AnyType(TypeOfAny.from_another_any, source_any=arg_type)
                    result = any_type, result[1]
            success = not local_errors.is_errors()
        else:
            error_any = AnyType(TypeOfAny.from_error)
            result = error_any, error_any
            success = False
        if success or not allow_reverse or isinstance(base_type, AnyType):
            # We were able to call the normal variant of the operator method,
            # or there was some problem not related to argument type
            # validity, or the operator has no __rX method. In any case, we
            # don't need to consider the __rX method.
            self.msg.add_errors(local_errors)
            return result
        else:
            # Calling the operator method was unsuccessful. Try the __rX
            # method of the other operand instead.
            rmethod = self.get_reverse_op_method(method)
            arg_type = self.accept(arg)
            base_arg_node = TempNode(base_type)
            # In order to be consistent with showing an error about the lhs not matching if neither
            # the lhs nor the rhs have a compatible signature, we keep track of the first error
            # message generated when considering __rX methods and __cmp__ methods for Python 2.
            first_error = None  # type: Optional[Tuple[Tuple[Type, Type], MessageBuilder]]
            if self.has_member(arg_type, rmethod):
                result, local_errors = self._check_op_for_errors(rmethod, arg_type,
                                                                 base_arg_node, context)
                if not local_errors.is_errors():
                    return result
                first_error = first_error or (result, local_errors)
            # If we've failed to find an __rX method and we're checking Python 2, check to see if
            # there is a __cmp__ method on the lhs or on the rhs.
            if (self.chk.options.python_version[0] == 2 and
                    method in nodes.ops_falling_back_to_cmp):
                cmp_method = nodes.comparison_fallback_method
                if self.has_member(base_type, cmp_method):
                    # First check the if the lhs has a __cmp__ method that works
                    result, local_errors = self._check_op_for_errors(cmp_method, base_type,
                                                                     arg, context)
                    if not local_errors.is_errors():
                        return result
                    first_error = first_error or (result, local_errors)
                if self.has_member(arg_type, cmp_method):
                    # Failed to find a __cmp__ method on the lhs, check if
                    # the rhs as a __cmp__ method that can operate on lhs
                    result, local_errors = self._check_op_for_errors(cmp_method, arg_type,
                                                                     base_arg_node, context)
                    if not local_errors.is_errors():
                        return result
                    first_error = first_error or (result, local_errors)
            if first_error:
                # We found either a __rX method, a __cmp__ method on the base_type, or a __cmp__
                # method on the rhs and failed match. Return the error for the first of these to
                # fail.
                self.msg.add_errors(first_error[1])
                return first_error[0]
            else:
                # No __rX method or __cmp__. Do deferred type checking to
                # produce error message that we may have missed previously.
                # TODO Fix type checking an expression more than once.
                return self.check_op_local(method, base_type, arg, context,
                                           self.msg)

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
        elif op == '-':
            method_type = self.analyze_external_member_access('__neg__',
                                                              operand_type, e)
            result, method_type = self.check_call(method_type, [], [], e)
            e.method_type = method_type
        elif op == '+':
            method_type = self.analyze_external_member_access('__pos__',
                                                              operand_type, e)
            result, method_type = self.check_call(method_type, [], [], e)
            e.method_type = method_type
        else:
            assert op == '~', "unhandled unary operator"
            method_type = self.analyze_external_member_access('__invert__',
                                                              operand_type, e)
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
        if 'unimported' in options.disallow_any and has_any_from_unimported_type(target_type):
            self.msg.unimported_type_becomes_any("Target type of cast", target_type, expr)
        check_for_explicit_any(target_type, self.chk.options, self.chk.is_typeshed_stub, self.msg,
                               context=expr)
        return target_type

    def visit_reveal_type_expr(self, expr: RevealTypeExpr) -> Type:
        """Type check a reveal_type expression."""
        revealed_type = self.accept(expr.expr, type_context=self.type_context[-1])
        if not self.chk.current_node_deferred:
            self.msg.reveal_type(revealed_type, expr)
            if not self.chk.in_checked_function():
                self.msg.note("'reveal_type' always outputs 'Any' in unchecked functions", expr)
        return revealed_type

    def visit_type_application(self, tapp: TypeApplication) -> Type:
        """Type check a type application (expr[type, ...])."""
        tp = self.accept(tapp.expr)
        if isinstance(tp, CallableType):
            if not tp.is_type_obj():
                self.chk.fail(messages.ONLY_CLASS_APPLICATION, tapp)
            if len(tp.variables) != len(tapp.types):
                self.msg.incompatible_type_application(len(tp.variables),
                                                       len(tapp.types), tapp)
                return AnyType(TypeOfAny.from_error)
            return self.apply_generic_arguments(tp, tapp.types, tapp)
        elif isinstance(tp, Overloaded):
            if not tp.is_type_obj():
                self.chk.fail(messages.ONLY_CLASS_APPLICATION, tapp)
            for item in tp.items():
                if len(item.variables) != len(tapp.types):
                    self.msg.incompatible_type_application(len(item.variables),
                                                           len(tapp.types), tapp)
                    return AnyType(TypeOfAny.from_error)
            return Overloaded([self.apply_generic_arguments(item, tapp.types, tapp)
                               for item in tp.items()])
        if isinstance(tp, AnyType):
            return AnyType(TypeOfAny.from_another_any, source_any=tp)
        return AnyType(TypeOfAny.special_form)

    def visit_type_alias_expr(self, alias: TypeAliasExpr) -> Type:
        """Get type of a type alias (could be generic) in a runtime expression."""
        if isinstance(alias.type, Instance) and alias.type.invalid:
            # An invalid alias, error already has been reported
            return AnyType(TypeOfAny.from_error)
        item = alias.type
        if not alias.in_runtime:
            # We don't replace TypeVar's with Any for alias used as Alias[T](42).
            item = set_any_tvars(item, alias.tvars, alias.line, alias.column)
        if isinstance(item, Instance):
            # Normally we get a callable type (or overloaded) with .is_type_obj() true
            # representing the class's constructor
            tp = type_object_type(item.type, self.named_type)
        else:
            # This type is invalid in most runtime contexts
            # and corresponding an error will be reported.
            return alias.fallback
        if isinstance(tp, CallableType):
            if len(tp.variables) != len(item.args):
                self.msg.incompatible_type_application(len(tp.variables),
                                                       len(item.args), item)
                return AnyType(TypeOfAny.from_error)
            return self.apply_generic_arguments(tp, item.args, item)
        elif isinstance(tp, Overloaded):
            for it in tp.items():
                if len(it.variables) != len(item.args):
                    self.msg.incompatible_type_application(len(it.variables),
                                                           len(item.args), item)
                    return AnyType(TypeOfAny.from_error)
            return Overloaded([self.apply_generic_arguments(it, item.args, item)
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
        tvdef = TypeVarDef('T', -1, [], self.object_type())
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
        ktdef = TypeVarDef('KT', -1, [], self.object_type())
        vtdef = TypeVarDef('VT', -2, [], self.object_type())
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
                arg_kinds=arg_kinds
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
            typ = 'typing.AsyncIterator'
        else:
            typ = 'typing.Iterator'
        return self.check_generator_or_comprehension(e, typ, '<generator>')

    def check_generator_or_comprehension(self, gen: GeneratorExpr,
                                         type_name: str,
                                         id_for_messages: str) -> Type:
        """Type check a generator expression or a list comprehension."""
        with self.chk.binder.frame_context(can_skip=True, fall_through=0):
            self.check_for_comp(gen)

            # Infer the type of the list comprehension by using a synthetic generic
            # callable type.
            tvdef = TypeVarDef('T', -1, [], self.object_type())
            tv = TypeVarType(tvdef)
            constructor = CallableType(
                [tv],
                [nodes.ARG_POS],
                [None],
                self.chk.named_generic_type(type_name, [tv]),
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
            ktdef = TypeVarDef('KT', -1, [], self.object_type())
            vtdef = TypeVarDef('VT', -2, [], self.object_type())
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
                sequence_type = self.chk.analyze_async_iterable_item_type(sequence)
            else:
                sequence_type = self.chk.analyze_iterable_item_type(sequence)
            self.chk.analyze_index_variables(index, sequence_type, True, e)
            for condition in conditions:
                self.accept(condition)

                # values are only part of the comprehension when all conditions are true
                true_map, _ = mypy.checker.find_isinstance_check(condition, self.chk.type_map)

                if true_map:
                    for var, type in true_map.items():
                        self.chk.binder.put(var, type)

    def visit_conditional_expr(self, e: ConditionalExpr) -> Type:
        cond_type = self.accept(e.cond)
        if self.chk.options.strict_boolean:
            is_bool = (isinstance(cond_type, Instance)
                and cond_type.type.fullname() == 'builtins.bool')
            if not (is_bool or isinstance(cond_type, AnyType)):
                self.chk.fail(messages.NON_BOOLEAN_IN_CONDITIONAL, e)
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

        if ('expr' in self.chk.options.disallow_any and
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
        # TODO TupleType => also consider tuple attributes
        if isinstance(typ, Instance):
            return typ.type.has_readable_member(member)
        if isinstance(typ, CallableType) and typ.is_type_obj():
            return typ.fallback.type.has_readable_member(member)
        elif isinstance(typ, AnyType):
            return True
        elif isinstance(typ, UnionType):
            result = all(self.has_member(x, member) for x in typ.relevant_items())
            return result
        elif isinstance(typ, TupleType):
            return self.has_member(typ.fallback, member)
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
            if ('unimported' in self.chk.options.disallow_any and
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
                        # Inline TypeCheker.set_inferred_type(),
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
            if restriction:
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
    return isinstance(t, Instance) and t.type.fullname() == 'typing.Awaitable'


def map_actuals_to_formals(caller_kinds: List[int],
                           caller_names: Optional[Sequence[Optional[str]]],
                           callee_kinds: List[int],
                           callee_names: List[Optional[str]],
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


def overload_arg_similarity(actual: Type, formal: Type) -> int:
    """Return if caller argument (actual) is compatible with overloaded signature arg (formal).

    Return a similarity level:
      0: no match
      1: actual is compatible, but only using type promotions (e.g. int vs float)
      2: actual is compatible without type promotions (e.g. int vs object)

    The distinction is important in cases where multiple overload items match. We want
    give priority to higher similarity matches.
    """
    # Replace type variables with their upper bounds. Overloading
    # resolution is based on runtime behavior which erases type
    # parameters, so no need to handle type variables occurring within
    # a type.
    if isinstance(actual, TypeVarType):
        actual = actual.erase_to_union_or_bound()
    if isinstance(formal, TypeVarType):
        formal = formal.erase_to_union_or_bound()
    if (isinstance(actual, UninhabitedType) or isinstance(actual, AnyType) or
            isinstance(formal, AnyType) or
            (isinstance(actual, Instance) and actual.type.fallback_to_any)):
        # These could match anything at runtime.
        return 2
    if isinstance(formal, CallableType):
        if isinstance(actual, (CallableType, Overloaded)):
            # TODO: do more sophisticated callable matching
            return 2
        if isinstance(actual, TypeType):
            return 2 if is_subtype(actual, formal) else 0
    if isinstance(actual, NoneTyp):
        if not experiments.STRICT_OPTIONAL:
            # NoneTyp matches anything if we're not doing strict Optional checking
            return 2
        else:
            # NoneType is a subtype of object
            if isinstance(formal, Instance) and formal.type.fullname() == "builtins.object":
                return 2
    if isinstance(actual, UnionType):
        return max(overload_arg_similarity(item, formal)
                   for item in actual.relevant_items())
    if isinstance(formal, UnionType):
        return max(overload_arg_similarity(actual, item)
                   for item in formal.relevant_items())
    if isinstance(formal, TypeType):
        if isinstance(actual, TypeType):
            # Since Type[T] is covariant, check if actual = Type[A] is
            # a subtype of formal = Type[F].
            return overload_arg_similarity(actual.item, formal.item)
        elif isinstance(actual, FunctionLike) and actual.is_type_obj():
            # Check if the actual is a constructor of some sort.
            # Note that this is this unsound, since we don't check the __init__ signature.
            return overload_arg_similarity(actual.items()[0].ret_type, formal.item)
        else:
            return 0
    if isinstance(actual, TypedDictType):
        if isinstance(formal, TypedDictType):
            # Don't support overloading based on the keys or value types of a TypedDict since
            # that would be complicated and probably only marginally useful.
            return 2
        return overload_arg_similarity(actual.fallback, formal)
    if isinstance(formal, Instance):
        if isinstance(actual, CallableType):
            actual = actual.fallback
        if isinstance(actual, Overloaded):
            actual = actual.items()[0].fallback
        if isinstance(actual, TupleType):
            actual = actual.fallback
        if isinstance(actual, Instance):
            # First perform a quick check (as an optimization) and fall back to generic
            # subtyping algorithm if type promotions are possible (e.g., int vs. float).
            if formal.type in actual.type.mro:
                return 2
            elif formal.type.is_protocol and is_subtype(actual, erasetype.erase_type(formal)):
                return 2
            elif actual.type._promote and is_subtype(actual, formal):
                return 1
            else:
                return 0
        elif isinstance(actual, TypeType):
            item = actual.item
            if formal.type.fullname() in {"builtins.object", "builtins.type"}:
                return 2
            elif isinstance(item, Instance) and item.type.metaclass_type:
                # FIX: this does not handle e.g. Union of instances
                return overload_arg_similarity(item.type.metaclass_type, formal)
            else:
                return 0
        else:
            return 0
    if isinstance(actual, UnboundType) or isinstance(formal, UnboundType):
        # Either actual or formal is the result of an error; shut up.
        return 2
    # Fall back to a conservative equality check for the remaining kinds of type.
    return 2 if is_same_type(erasetype.erase_type(actual), erasetype.erase_type(formal)) else 0


def any_arg_causes_overload_ambiguity(items: List[CallableType],
                                      arg_types: List[Type],
                                      arg_kinds: List[int],
                                      arg_names: Optional[Sequence[Optional[str]]]) -> bool:
    """May an Any actual argument cause ambiguous result type on call to overloaded function?

    Note that this sometimes returns True even if there is no ambiguity, since a correct
    implementation would be complex (and the call would be imprecisely typed due to Any
    types anyway).

    Args:
        items: Overload items matching the actual arguments
        arg_types: Actual argument types
        arg_kinds: Actual argument kinds
        arg_names: Actual argument names
    """
    actual_to_formal = [
        map_formals_to_actuals(
            arg_kinds, arg_names, item.arg_kinds, item.arg_names, lambda i: arg_types[i])
        for item in items
    ]

    for arg_idx, arg_type in enumerate(arg_types):
        if isinstance(arg_type, AnyType):
            matching_formals_unfiltered = [(item_idx, lookup[arg_idx])
                                           for item_idx, lookup in enumerate(actual_to_formal)
                                           if lookup[arg_idx]]
            matching_formals = []
            for item_idx, formals in matching_formals_unfiltered:
                if len(formals) > 1:
                    # An actual maps to multiple formals -- give up as too
                    # complex, just assume it overlaps.
                    return True
                matching_formals.append((item_idx, items[item_idx].arg_types[formals[0]]))
            if (not all_same_types(t for _, t in matching_formals) and
                    not all_same_types(items[idx].ret_type
                                       for idx, _ in matching_formals)):
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
