"""Expression type checker. This file is conceptually part of TypeChecker."""

from typing import Undefined, cast, List, Tuple, Dict, Function

from mypy.types import (
    Type, AnyType, Callable, Overloaded, NoneTyp, Void, TypeVarDef,
    TupleType, Instance, TypeVar, TypeTranslator, ErasedType, FunctionLike, UnionType
)
from mypy.nodes import (
    NameExpr, RefExpr, Var, FuncDef, OverloadedFuncDef, TypeInfo, CallExpr,
    Node, MemberExpr, IntExpr, StrExpr, BytesExpr, UnicodeExpr, FloatExpr,
    OpExpr, UnaryExpr, IndexExpr, CastExpr, TypeApplication, ListExpr,
    TupleExpr, DictExpr, FuncExpr, SuperExpr, ParenExpr, SliceExpr, Context,
    ListComprehension, GeneratorExpr, SetExpr, MypyFile, Decorator,
    UndefinedExpr, ConditionalExpr, ComparisonExpr, TempNode, LITERAL_TYPE
)
from mypy.errors import Errors
from mypy.nodes import function_type, method_type
from mypy import nodes
import mypy.checker
from mypy import types
from mypy.sametypes import is_same_type
from mypy.replacetvars import replace_func_type_vars, replace_type_vars
from mypy.messages import MessageBuilder
from mypy import messages
from mypy.infer import infer_type_arguments, infer_function_type_arguments
from mypy import join
from mypy.expandtype import expand_type, expand_caller_var_args
from mypy.subtypes import is_subtype
from mypy import applytype
from mypy import erasetype
from mypy.checkmember import analyse_member_access, type_object_type
from mypy.semanal import self_type
from mypy.constraints import get_actual_type
from mypy.checkstrformat import StringFormatterChecker


class ExpressionChecker:
    """Expression type checker.

    This class works closely together with checker.TypeChecker.
    """

    # Some services are provided by a TypeChecker instance.
    chk = Undefined('mypy.checker.TypeChecker')
    # This is shared with TypeChecker, but stored also here for convenience.
    msg = Undefined(MessageBuilder)

    strfrm_checker = Undefined('mypy.checkstrformat.StringFormatterChecker')

    def __init__(self,
                 chk: 'mypy.checker.TypeChecker',
                 msg: MessageBuilder) -> None:
        """Construct an expression type checker."""
        self.chk = chk
        self.msg = msg
        self.strfrm_checker = mypy.checkexpr.StringFormatterChecker(self, self.chk, self.msg)

    def visit_name_expr(self, e: NameExpr) -> Type:
        """Type check a name expression.

        It can be of any kind: local, member or global.
        """
        result = self.analyse_ref_expr(e)
        return self.chk.narrow_type_from_binder(e, result)

    def analyse_ref_expr(self, e: RefExpr) -> Type:
        result = Undefined(Type)
        node = e.node
        if isinstance(node, Var):
            # Variable reference.
            result = self.analyse_var_ref(node, e)
        elif isinstance(node, FuncDef):
            # Reference to a global function.
            result = function_type(node, self.named_type('builtins.function'))
        elif isinstance(node, OverloadedFuncDef):
            result = node.type
        elif isinstance(node, TypeInfo):
            # Reference to a type object.
            result = type_object_type(node, self.named_type)
        elif isinstance(node, MypyFile):
            # Reference to a module object.
            result = self.named_type('builtins.module')
        elif isinstance(node, Decorator):
            result = self.analyse_var_ref(node.var, e)
        else:
            # Unknown reference; use any type implicitly to avoid
            # generating extra type errors.
            result = AnyType()
        return result

    def analyse_var_ref(self, var: Var, context: Context) -> Type:
        if not var.type:
            if not var.is_ready:
                self.msg.cannot_determine_type(var.name(), context)
            # Implicit 'Any' type.
            return AnyType()
        else:
            # Look up local type of variable with type (inferred or explicit).
            val = self.chk.binder.get(var)
            if val is None:
                return var.type
            else:
                return val

    def visit_call_expr(self, e: CallExpr) -> Type:
        """Type check a call expression."""
        if e.analyzed:
            # It's really a special form that only looks like a call.
            return self.accept(e.analyzed)
        self.accept(e.callee)
        # Access callee type directly, since accept may return the Any type
        # even if the type is known (in a dynamically typed function). This
        # way we get a more precise callee in dynamically typed functions.
        callee_type = self.chk.type_map[e.callee]
        return self.check_call_expr_with_callee_type(callee_type, e)

    def check_call_expr_with_callee_type(self, callee_type: Type,
                                         e: CallExpr) -> Type:
        """Type check call expression.

        The given callee type overrides the type of the callee
        expression.
        """
        return self.check_call(callee_type, e.args, e.arg_kinds, e,
                               e.arg_names, callable_node=e.callee)[0]

    def check_call(self, callee: Type, args: List[Node],
                   arg_kinds: List[int], context: Context,
                   arg_names: List[str] = None,
                   callable_node: Node = None,
                   arg_messages: MessageBuilder = None) -> Tuple[Type, Type]:
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
        """
        arg_messages = arg_messages or self.msg
        is_var_arg = nodes.ARG_STAR in arg_kinds
        if isinstance(callee, Callable):
            if callee.is_type_obj():
                t = callee.type_object()
            if callee.is_type_obj() and callee.type_object().is_abstract:
                type = callee.type_object()
                self.msg.cannot_instantiate_abstract_class(
                    callee.type_object().name(), type.abstract_attributes,
                    context)

            formal_to_actual = map_actuals_to_formals(
                arg_kinds, arg_names,
                callee.arg_kinds, callee.arg_names,
                lambda i: self.accept(args[i]))

            if callee.is_generic():
                callee = self.infer_function_type_arguments_using_context(
                    callee, context)
                callee = self.infer_function_type_arguments(
                    callee, args, arg_kinds, formal_to_actual, context)

            arg_types = self.infer_arg_types_in_context2(
                callee, args, arg_kinds, formal_to_actual)

            self.check_argument_count(callee, arg_types, arg_kinds,
                                      arg_names, formal_to_actual, context)

            self.check_argument_types(arg_types, arg_kinds, callee,
                                      formal_to_actual, context,
                                      messages=arg_messages)
            if callable_node:
                # Store the inferred callable type.
                self.chk.store_type(callable_node, callee)
            return callee.ret_type, callee
        elif isinstance(callee, Overloaded):
            # Type check arguments in empty context. They will be checked again
            # later in a context derived from the signature; these types are
            # only used to pick a signature variant.
            self.msg.disable_errors()
            arg_types = self.infer_arg_types_in_context(None, args)
            self.msg.enable_errors()

            target = self.overload_call_target(arg_types, is_var_arg,
                                               callee, context,
                                               messages=arg_messages)
            return self.check_call(target, args, arg_kinds, context, arg_names,
                                   arg_messages=arg_messages)
        elif isinstance(callee, AnyType) or self.chk.is_dynamic_function():
            self.infer_arg_types_in_context(None, args)
            return AnyType(), AnyType()
        elif isinstance(callee, UnionType):
            self.msg.disable_type_names += 1
            results = [self.check_call(subtype, args, arg_kinds, context, arg_names,
                                       arg_messages=arg_messages)
                       for subtype in callee.items]
            self.msg.disable_type_names -= 1
            return (UnionType.make_simplified_union([res[0] for res in results]),
                    callee)
        else:
            return self.msg.not_callable(callee, context), AnyType()

    def infer_arg_types_in_context(self, callee: Callable,
                                   args: List[Node]) -> List[Type]:
        """Infer argument expression types using a callable type as context.

        For example, if callee argument 2 has type List[int], infer the
        argument expression with List[int] type context.
        """
        # TODO Always called with callee as None, i.e. empty context.
        res = []  # type: List[Type]

        fixed = len(args)
        if callee:
            fixed = min(fixed, callee.max_fixed_args())

        arg_type = None  # type: Type
        ctx = None  # type: Type
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
            if isinstance(arg_type, ErasedType):
                res.append(NoneTyp())
            else:
                res.append(arg_type)
        return res

    def infer_arg_types_in_context2(
            self, callee: Callable, args: List[Node], arg_kinds: List[int],
            formal_to_actual: List[List[int]]) -> List[Type]:
        """Infer argument expression types using a callable type as context.

        For example, if callee argument 2 has type List[int], infer the
        argument exprsession with List[int] type context.

        Returns the inferred types of *actual arguments*.
        """
        res = [None] * len(args)  # type: List[Type]

        for i, actuals in enumerate(formal_to_actual):
            for ai in actuals:
                if arg_kinds[ai] != nodes.ARG_STAR:
                    res[ai] = self.accept(args[ai], callee.arg_types[i])

        # Fill in the rest of the argument types.
        for i, t in enumerate(res):
            if not t:
                res[i] = self.accept(args[i])
        return res

    def infer_function_type_arguments_using_context(
            self, callable: Callable, error_context: Context) -> Callable:
        """Unify callable return type to type context to infer type vars.

        For example, if the return type is set[t] where 't' is a type variable
        of callable, and if the context is set[int], return callable modified
        by substituting 't' with 'int'.
        """
        ctx = self.chk.type_context[-1]
        if not ctx:
            return callable
        # The return type may have references to function type variables that
        # we are inferring right now. We must consider them as indeterminate
        # and they are not potential results; thus we replace them with the
        # special ErasedType type. On the other hand, class type variables are
        # valid results.
        erased_ctx = replace_func_type_vars(ctx, ErasedType())
        ret_type = callable.ret_type
        if isinstance(ret_type, TypeVar):
            if ret_type.values or (not isinstance(ctx, Instance) or
                                   not cast(Instance, ctx).args):
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
        # Only substite non-None and non-erased types.
        new_args = []  # type: List[Type]
        for arg in args:
            if isinstance(arg, NoneTyp) or has_erased_component(arg):
                new_args.append(None)
            else:
                new_args.append(arg)
        return cast(Callable, self.apply_generic_arguments(callable, new_args,
                                                           error_context))

    def infer_function_type_arguments(self, callee_type: Callable,
                                      args: List[Node],
                                      arg_kinds: List[int],
                                      formal_to_actual: List[List[int]],
                                      context: Context) -> Callable:
        """Infer the type arguments for a generic callee type.

        Infer based on the types of arguments.

        Return a derived callable type that has the arguments applied (and
        stored as implicit type arguments).
        """
        if not self.chk.is_dynamic_function():
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

            pass1_args = []  # type: List[Type]
            for i, arg in enumerate(arg_types):
                if arg_pass_nums[i] > 1:
                    pass1_args.append(None)
                else:
                    pass1_args.append(arg)

            inferred_args = infer_function_type_arguments(
                callee_type, pass1_args, arg_kinds, formal_to_actual)  # type: List[Type]

            if 2 in arg_pass_nums:
                # Second pass of type inference.
                (callee_type,
                 inferred_args) = self.infer_function_type_arguments_pass2(
                    callee_type, args, arg_kinds, formal_to_actual,
                    inferred_args, context)
        else:
            # In dynamically typed functions use implicit 'Any' types for
            # type variables.
            inferred_args = [AnyType()] * len(callee_type.variables)
        return self.apply_inferred_arguments(callee_type, inferred_args,
                                             context)

    def infer_function_type_arguments_pass2(
            self, callee_type: Callable,
            args: List[Node],
            arg_kinds: List[int],
            formal_to_actual: List[List[int]],
            inferred_args: List[Type],
            context: Context) -> Tuple[Callable, List[Type]]:
        """Perform second pass of generic function type argument inference.

        The second pass is needed for arguments with types such as func<s(t)>,
        where both s and t are type variables, when the actual argument is a
        lambda with inferred types.  The idea is to infer the type variable t
        in the first pass (based on the types of other arguments).  This lets
        us infer the argument and return type of the lambda expression and
        thus also the type variable s in this second pass.

        Return (the callee with type vars applied, inferred actual arg types).
        """
        # None or erased types in inferred types mean that there was not enough
        # information to infer the argument. Replace them with None values so
        # that they are not applied yet below.
        for i, arg in enumerate(inferred_args):
            if isinstance(arg, NoneTyp) or isinstance(arg, ErasedType):
                inferred_args[i] = None

        callee_type = cast(Callable, self.apply_generic_arguments(
            callee_type, inferred_args, context))
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

    def apply_inferred_arguments(self, callee_type: Callable,
                                 inferred_args: List[Type],
                                 context: Context) -> Callable:
        """Apply inferred values of type arguments to a generic function.

        Inferred_args contains the values of function type arguments.
        """
        # Report error if some of the variables could not be solved. In that
        # case assume that all variables have type Any to avoid extra
        # bogus error messages.
        for i, inferred_type in enumerate(inferred_args):
            if not inferred_type:
                # Could not infer a non-trivial type for a type variable.
                self.msg.could_not_infer_type_arguments(
                    callee_type, i + 1, context)
                inferred_args = [AnyType()] * len(inferred_args)
        # Apply the inferred types to the function type. In this case the
        # return type must be Callable, since we give the right number of type
        # arguments.
        return cast(Callable, self.apply_generic_arguments(callee_type,
                                                           inferred_args, context))

    def check_argument_count(self, callee: Callable, actual_types: List[Type],
                             actual_kinds: List[int], actual_names: List[str],
                             formal_to_actual: List[List[int]],
                             context: Context) -> None:
        """Check that the number of arguments to a function are valid.

        Also check that there are no duplicate values for arguments.
        """
        formal_kinds = callee.arg_kinds

        # Collect list of all actual arguments matched to formal arguments.
        all_actuals = []  # type: List[int]
        for actuals in formal_to_actual:
            all_actuals.extend(actuals)

        is_error = False  # Keep track of errors to avoid duplicate errors.
        for i, kind in enumerate(actual_kinds):
            if i not in all_actuals and (
                    kind != nodes.ARG_STAR or
                    not is_empty_tuple(actual_types[i])):
                # Extra actual: not matched by a formal argument.
                if kind != nodes.ARG_NAMED:
                    self.msg.too_many_arguments(callee, context)
                else:
                    self.msg.unexpected_keyword_argument(
                        callee, actual_names[i], context)
                    is_error = True
            elif kind == nodes.ARG_STAR and (
                    nodes.ARG_STAR not in formal_kinds):
                actual_type = actual_types[i]
                if isinstance(actual_type, TupleType):
                    if all_actuals.count(i) < len(actual_type.items):
                        # Too many tuple items as some did not match.
                        self.msg.too_many_arguments(callee, context)
                # *args can be applied even if the function takes a fixed
                # number of positional arguments. This may succeed at runtime.

        for i, kind in enumerate(formal_kinds):
            if kind == nodes.ARG_POS and (not formal_to_actual[i] and
                                          not is_error):
                # No actual for a mandatory positional formal.
                self.msg.too_few_arguments(callee, context)
            elif kind in [nodes.ARG_POS, nodes.ARG_OPT,
                          nodes.ARG_NAMED] and is_duplicate_mapping(
                    formal_to_actual[i], actual_kinds):
                self.msg.duplicate_argument_value(callee, i, context)
            elif (kind == nodes.ARG_NAMED and formal_to_actual[i] and
                  actual_kinds[formal_to_actual[i][0]] != nodes.ARG_NAMED):
                # Positional argument when expecting a keyword argument.
                self.msg.too_many_positional_arguments(callee, context)

    def check_argument_types(self, arg_types: List[Type], arg_kinds: List[int],
                             callee: Callable,
                             formal_to_actual: List[List[int]],
                             context: Context,
                             messages: MessageBuilder = None) -> None:
        """Check argument types against a callable type.

        Report errors if the argument types are not compatible.
        """
        messages = messages or self.msg
        # Keep track of consumed tuple *arg items.
        tuple_counter = [0]
        for i, actuals in enumerate(formal_to_actual):
            for actual in actuals:
                arg_type = arg_types[actual]
                # Check that a *arg is valid as varargs.
                if (arg_kinds[actual] == nodes.ARG_STAR and
                        not self.is_valid_var_arg(arg_type)):
                    messages.invalid_var_arg(arg_type, context)
                if (arg_kinds[actual] == nodes.ARG_STAR2 and
                        not self.is_valid_keyword_var_arg(arg_type)):
                    messages.invalid_keyword_var_arg(arg_type, context)
                # Get the type of an inidividual actual argument (for *args
                # and **args this is the item type, not the collection type).
                actual_type = get_actual_type(arg_type, arg_kinds[actual],
                                              tuple_counter)
                self.check_arg(actual_type, arg_type,
                               callee.arg_types[i],
                               actual + 1, callee, context, messages)

                # There may be some remaining tuple varargs items that haven't
                # been checked yet. Handle them.
                if (callee.arg_kinds[i] == nodes.ARG_STAR and
                        arg_kinds[actual] == nodes.ARG_STAR and
                        isinstance(arg_types[actual], TupleType)):
                    tuplet = cast(TupleType, arg_types[actual])
                    while tuple_counter[0] < len(tuplet.items):
                        actual_type = get_actual_type(arg_type,
                                                      arg_kinds[actual],
                                                      tuple_counter)
                        self.check_arg(actual_type, arg_type,
                                       callee.arg_types[i],
                                       actual + 1, callee, context, messages)

    def check_arg(self, caller_type: Type, original_caller_type: Type,
                  callee_type: Type, n: int, callee: Callable,
                  context: Context, messages: MessageBuilder) -> None:
        """Check the type of a single argument in a call."""
        if isinstance(caller_type, Void):
            messages.does_not_return_value(caller_type, context)
        elif not is_subtype(caller_type, callee_type):
            messages.incompatible_argument(n, callee, original_caller_type,
                                           context)

    def overload_call_target(self, arg_types: List[Type], is_var_arg: bool,
                             overload: Overloaded, context: Context,
                             messages: MessageBuilder = None) -> Type:
        """Infer the correct overload item to call with given argument types.

        The return value may be Callable or AnyType (if an unique item
        could not be determined). If is_var_arg is True, the caller
        uses varargs.
        """
        messages = messages or self.msg
        # TODO also consider argument names and kinds
        # TODO for overlapping signatures we should try to get a more precise
        #      result than 'Any'
        match = []  # type: List[Callable]
        for typ in overload.items():
            if self.matches_signature_erased(arg_types, is_var_arg, typ):
                if (match and not is_same_type(match[-1].ret_type,
                                               typ.ret_type) and
                    not mypy.checker.is_more_precise_signature(
                        match[-1], typ)):
                    # Ambiguous return type. Either the function overload is
                    # overlapping (which results in an error elsewhere) or the
                    # caller has provided some Any argument types; in
                    # either case can only infer the type to be Any, as it is
                    # not an error to use Any types in calls.
                    #
                    # Overlapping overload items are fine if the items are
                    # covariant in both argument types and return types with
                    # respect to type precision.
                    return AnyType()
                else:
                    match.append(typ)
        if not match:
            messages.no_variant_matches_arguments(overload, context)
            return AnyType()
        else:
            if len(match) == 1:
                return match[0]
            else:
                # More than one signature matches. Pick the first *non-erased*
                # matching signature, or default to the first one if none
                # match.
                for m in match:
                    if self.match_signature_types(arg_types, is_var_arg, m):
                        return m
                return match[0]

    def matches_signature_erased(self, arg_types: List[Type], is_var_arg: bool,
                                 callee: Callable) -> bool:
        """Determine whether arguments could match the signature at runtime.

        If is_var_arg is True, the caller uses varargs. This is used for
        overload resolution.
        """
        if not is_valid_argc(len(arg_types), False, callee):
            return False

        if is_var_arg:
            if not self.is_valid_var_arg(arg_types[-1]):
                return False
            arg_types, rest = expand_caller_var_args(arg_types,
                                                     callee.max_fixed_args())

        # Fixed function arguments.
        func_fixed = callee.max_fixed_args()
        for i in range(min(len(arg_types), func_fixed)):
            if not is_subtype(self.erase(arg_types[i]),
                              self.erase(
                                  callee.arg_types[i])):
                return False
        # Function varargs.
        if callee.is_var_arg:
            for i in range(func_fixed, len(arg_types)):
                if not is_subtype(self.erase(arg_types[i]),
                                  self.erase(callee.arg_types[func_fixed])):
                    return False
        return True

    def match_signature_types(self, arg_types: List[Type], is_var_arg: bool,
                              callee: Callable) -> bool:
        """Determine whether arguments types match the signature.

        If is_var_arg is True, the caller uses varargs. Assume that argument
        counts are compatible.
        """
        if is_var_arg:
            arg_types, rest = expand_caller_var_args(arg_types,
                                                     callee.max_fixed_args())

        # Fixed function arguments.
        func_fixed = callee.max_fixed_args()
        for i in range(min(len(arg_types), func_fixed)):
            if not is_subtype(arg_types[i], callee.arg_types[i]):
                return False
        # Function varargs.
        if callee.is_var_arg:
            for i in range(func_fixed, len(arg_types)):
                if not is_subtype(arg_types[i],
                                  callee.arg_types[func_fixed]):
                    return False
        return True

    def apply_generic_arguments(self, callable: Callable, types: List[Type],
                                context: Context) -> Type:
        """Simple wrapper around mypy.applytype.apply_generic_arguments."""
        return applytype.apply_generic_arguments(callable, types, self.msg, context)

    def apply_generic_arguments2(self, overload: Overloaded, types: List[Type],
                                 context: Context) -> Type:
        items = []  # type: List[Callable]
        for item in overload.items():
            applied = self.apply_generic_arguments(item, types, context)
            if isinstance(applied, Callable):
                items.append(applied)
            else:
                # There was an error.
                return AnyType()
        return Overloaded(items)

    def visit_member_expr(self, e: MemberExpr) -> Type:
        """Visit member expression (of form e.id)."""
        result = self.analyse_ordinary_member_access(e, False)
        return self.chk.narrow_type_from_binder(e, result)

    def analyse_ordinary_member_access(self, e: MemberExpr,
                                       is_lvalue: bool) -> Type:
        """Analyse member expression or member lvalue."""
        if e.kind is not None:
            # This is a reference to a module attribute.
            return self.analyse_ref_expr(e)
        else:
            # This is a reference to a non-module attribute.
            return analyse_member_access(e.name, self.accept(e.expr), e,
                                         is_lvalue, False,
                                         self.named_type, self.msg)

    def analyse_external_member_access(self, member: str, base_type: Type,
                                       context: Context) -> Type:
        """Analyse member access that is external, i.e. it cannot
        refer to private definitions. Return the result type.
        """
        # TODO remove; no private definitions in mypy
        return analyse_member_access(member, base_type, context, False, False,
                                     self.named_type, self.msg)

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

    def visit_op_expr(self, e: OpExpr) -> Type:
        """Type check a binary operator expression."""
        if e.op == 'and' or e.op == 'or':
            return self.check_boolean_op(e, e)
        if e.op == '*' and isinstance(e.left, ListExpr):
            # Expressions of form [...] * e get special type inference.
            return self.check_list_multiply(e)
        if e.op == '%' and isinstance(e.left, StrExpr):
            return self.strfrm_checker.check_str_interpolation(cast(StrExpr, e.left), e.right)
        left_type = self.accept(e.left)

        if e.op in nodes.op_methods:
            method = self.get_operator_method(e.op)
            result, method_type = self.check_op(method, left_type, e.right, e,
                                                allow_reverse=True)
            e.method_type = method_type
            return result
        else:
            raise RuntimeError('Unknown operator {}'.format(e.op))

    def strip_parens(self, node: Node) -> Node:
        if isinstance(node, ParenExpr):
            return self.strip_parens(node.expr)
        else:
            return node

    def visit_comparison_expr(self, e: ComparisonExpr) -> Type:
        """Type check a comparison expression.

        Comparison expressions are type checked consecutive-pair-wise
        That is, 'a < b > c == d' is check as 'a < b and b > c and c == d'
        """
        result = None  # type: mypy.types.Type

        # Check each consecutive operand pair and their operator
        for left, right, operator in zip(e.operands, e.operands[1:], e.operators):
            left_type = self.accept(left)

            method_type = None  # type: mypy.types.Type

            if operator == 'in' or operator == 'not in':
                right_type = self.accept(right)  # TODO only evaluate if needed

                local_errors = self.msg.copy()
                sub_result, method_type = self.check_op_local('__contains__', right_type,
                                                          left, e, local_errors)
                if (local_errors.is_errors() and
                    # is_valid_var_arg is True for any Iterable
                        self.is_valid_var_arg(right_type)):
                    itertype = self.chk.analyse_iterable_item_type(right)
                    method_type = Callable([left_type],
                                           [nodes.ARG_POS],
                                           [None],
                                           self.chk.bool_type(),
                                           self.named_type('builtins.function'))
                    sub_result = self.chk.bool_type()
                    if not is_subtype(left_type, itertype):
                        self.msg.unsupported_operand_types('in', left_type, right_type, e)
                else:
                    self.msg.add_errors(local_errors)
                if operator == 'not in':
                    sub_result = self.chk.bool_type()
            elif operator in nodes.op_methods:
                method = self.get_operator_method(operator)
                sub_result, method_type = self.check_op(method, left_type, right, e,
                                                    allow_reverse=True)

            elif operator == 'is' or operator == 'is not':
                sub_result = self.chk.bool_type()
                method_type = None
            else:
                raise RuntimeError('Unknown comparison operator {}'.format(operator))

            e.method_types.append(method_type)

            #  Determine type of boolean-and of result and sub_result
            if result == None:
                result = sub_result
            else:
                # TODO: check on void needed?
                self.check_not_void(sub_result, e)
                result = join.join_types(result, sub_result)

        return result

    def get_operator_method(self, op: str) -> str:
        if op == '/' and self.chk.pyversion == 2:
            # TODO also check for "from __future__ import division"
            return '__div__'
        else:
            return nodes.op_methods[op]

    def check_op_local(self, method: str, base_type: Type, arg: Node,
                       context: Context, local_errors: MessageBuilder) -> Tuple[Type, Type]:
        """Type check a binary operation which maps to a method call.

        Return tuple (result type, inferred operator method type).
        """
        method_type = analyse_member_access(method, base_type, context, False, False,
                                            self.named_type, local_errors)
        return self.check_call(method_type, [arg], [nodes.ARG_POS],
                               context, arg_messages=local_errors)

    def check_op(self, method: str, base_type: Type, arg: Node,
                 context: Context,
                 allow_reverse: bool = False) -> Tuple[Type, Type]:
        """Type check a binary operation which maps to a method call.

        Return tuple (result type, inferred operator method type).
        """
        # Use a local error storage for errors related to invalid argument
        # type (but NOT other errors). This error may need to be suppressed
        # for operators which support __rX methods.
        local_errors = self.msg.copy()
        if not allow_reverse or self.has_member(base_type, method):
            result = self.check_op_local(method, base_type, arg, context,
                                         local_errors)
            if allow_reverse:
                arg_type = self.chk.type_map[arg]
                if isinstance(arg_type, AnyType):
                    # If the right operand has type Any, we can't make any
                    # conjectures about the type of the result, since the
                    # operand could have a __r method that returns anything.
                    result = AnyType(), result[1]
            success = not local_errors.is_errors()
        else:
            result = AnyType(), AnyType()
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
            if self.has_member(arg_type, rmethod):
                method_type = self.analyse_external_member_access(
                    rmethod, arg_type, context)
                temp = TempNode(base_type)
                return self.check_call(method_type, [temp], [nodes.ARG_POS],
                                       context)
            else:
                # No __rX method either. Do deferred type checking to produce
                # error message that we may have missed previously.
                # TODO Fix type checking an expression more than once.
                return self.check_op_local(method, base_type, arg, context,
                                           self.msg)

    def get_reverse_op_method(self, method: str) -> str:
        if method == '__div__' and self.chk.pyversion == 2:
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
        ctx = self.chk.type_context[-1]
        left_type = self.accept(e.left, ctx)
        right_type = self.accept(e.right, left_type)

        self.check_not_void(left_type, context)
        self.check_not_void(right_type, context)

        return join.join_types(left_type, right_type)

    def check_list_multiply(self, e: OpExpr) -> Type:
        """Type check an expression of form '[...] * e'.

        Type inference is special-cased for this common construct.
        """
        right_type = self.accept(e.right)
        if is_subtype(right_type, self.named_type('builtins.int')):
            # Special case: [...] * <int value>. Use the type context of the
            # OpExpr, since the multiplication does not affect the type.
            left_type = self.accept(e.left, context=self.chk.type_context[-1])
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
            self.check_not_void(operand_type, e)
            result = self.chk.bool_type()  # type: Type
        elif op == '-':
            method_type = self.analyse_external_member_access('__neg__',
                                                              operand_type, e)
            result, method_type = self.check_call(method_type, [], [], e)
            e.method_type = method_type
        elif op == '+':
            method_type = self.analyse_external_member_access('__pos__',
                                                              operand_type, e)
            result, method_type = self.check_call(method_type, [], [], e)
            e.method_type = method_type
        else:
            assert op == '~', "unhandled unary operator"
            method_type = self.analyse_external_member_access('__invert__',
                                                              operand_type, e)
            result, method_type = self.check_call(method_type, [], [], e)
            e.method_type = method_type
        return result

    def visit_index_expr(self, e: IndexExpr) -> Type:
        """Type check an index expression (base[index]).

        It may also represent type application.
        """
        result = self.visit_index_expr_helper(e)
        return self.chk.narrow_type_from_binder(e, result)

    def visit_index_expr_helper(self, e: IndexExpr) -> Type:
        if e.analyzed:
            # It's actually a type application.
            return self.accept(e.analyzed)
        left_type = self.accept(e.base)
        if isinstance(left_type, TupleType):
            # Special case for tuples. They support indexing only by integer
            # literals.
            index = self.strip_parens(e.index)
            ok = False
            if isinstance(index, IntExpr):
                n = index.value
                ok = True
            elif isinstance(index, UnaryExpr):
                if index.op == '-':
                    operand = index.expr
                    if isinstance(operand, IntExpr):
                        n = len(left_type.items) - operand.value
                        ok = True
            if ok:
                if n >= 0 and n < len(left_type.items):
                    return left_type.items[n]
                else:
                    self.chk.fail(messages.TUPLE_INDEX_OUT_OF_RANGE, e)
                    return AnyType()
            else:
                self.chk.fail(messages.TUPLE_INDEX_MUST_BE_AN_INT_LITERAL, e)
                return AnyType()
        else:
            result, method_type = self.check_op('__getitem__', left_type,
                                                e.index, e)
            e.method_type = method_type
            return result

    def visit_cast_expr(self, expr: CastExpr) -> Type:
        """Type check a cast expression."""
        source_type = self.accept(expr.expr)
        target_type = expr.type
        if not self.is_valid_cast(source_type, target_type):
            self.msg.invalid_cast(target_type, source_type, expr)
        return target_type

    def is_valid_cast(self, source_type: Type, target_type: Type) -> bool:
        """Is a cast from source_type to target_type meaningful?"""
        return (isinstance(target_type, AnyType) or
                (not isinstance(source_type, Void) and
                 not isinstance(target_type, Void)))

    def visit_type_application(self, tapp: TypeApplication) -> Type:
        """Type check a type application (expr[type, ...])."""
        expr_type = self.accept(tapp.expr)
        if isinstance(expr_type, Callable):
            new_type = self.apply_generic_arguments(expr_type,
                                                    tapp.types, tapp)
        elif isinstance(expr_type, Overloaded):
            overload = expr_type
            # Only target items with the right number of generic type args.
            items = [c for c in overload.items()
                     if len(c.variables) == len(tapp.types)]
            new_type = self.apply_generic_arguments2(Overloaded(items),
                                                     tapp.types, tapp)
        else:
            self.chk.fail(messages.INVALID_TYPE_APPLICATION_TARGET_TYPE, tapp)
            new_type = AnyType()
        self.chk.type_map[tapp.expr] = new_type
        return new_type

    def visit_list_expr(self, e: ListExpr) -> Type:
        """Type check a list expression [...]."""
        return self.check_list_or_set_expr(e.items, 'builtins.list', '<list>',
                                           e)

    def visit_set_expr(self, e: SetExpr) -> Type:
        return self.check_list_or_set_expr(e.items, 'builtins.set', '<set>', e)

    def check_list_or_set_expr(self, items: List[Node], fullname: str,
                               tag: str, context: Context) -> Type:
        # Translate into type checking a generic function call.
        tv = TypeVar('T', -1, [], self.chk.object_type())
        constructor = Callable([tv],
                               [nodes.ARG_STAR],
                               [None],
                               self.chk.named_generic_type(fullname,
                                                           [tv]),
                               self.named_type('builtins.function'),
                               tag,
                               [TypeVarDef('T', -1, None, self.chk.object_type())])
        return self.check_call(constructor,
                               items,
                               [nodes.ARG_POS] * len(items), context)[0]

    def visit_tuple_expr(self, e: TupleExpr) -> Type:
        """Type check a tuple expression."""
        ctx = None  # type: TupleType
        # Try to determine type context for type inference.
        if isinstance(self.chk.type_context[-1], TupleType):
            t = cast(TupleType, self.chk.type_context[-1])
            if len(t.items) == len(e.items):
                ctx = t
        # Infer item types.
        items = []  # type: List[Type]
        for i in range(len(e.items)):
            item = e.items[i]
            tt = Undefined  # type: Type
            if not ctx:
                tt = self.accept(item)
            else:
                tt = self.accept(item, ctx.items[i])
            self.check_not_void(tt, e)
            items.append(tt)
        return TupleType(items, self.named_type('builtins.tuple'))

    def visit_dict_expr(self, e: DictExpr) -> Type:
        # Translate into type checking a generic function call.
        tv1 = TypeVar('KT', -1, [], self.chk.object_type())
        tv2 = TypeVar('VT', -2, [], self.chk.object_type())
        constructor = Undefined(Callable)
        # The callable type represents a function like this:
        #
        #   def <unnamed>(*v: Tuple[kt, vt]) -> Dict[kt, vt]: ...
        constructor = Callable([TupleType([tv1, tv2], self.named_type('builtins.tuple'))],
                               [nodes.ARG_STAR],
                               [None],
                               self.chk.named_generic_type('builtins.dict',
                                                           [tv1, tv2]),
                               self.named_type('builtins.function'),
                               '<list>',
                               [TypeVarDef('KT', -1, None, self.chk.object_type()),
                                TypeVarDef('VT', -2, None, self.chk.object_type())])
        # Synthesize function arguments.
        args = List[Node]()
        for key, value in e.items:
            args.append(TupleExpr([key, value]))
        return self.check_call(constructor,
                               args,
                               [nodes.ARG_POS] * len(args), e)[0]

    def visit_func_expr(self, e: FuncExpr) -> Type:
        """Type check lambda expression."""
        inferred_type = self.infer_lambda_type_using_context(e)
        if not inferred_type:
            # No useful type context.
            ret_type = e.expr().accept(self.chk)
            if not e.args:
                # Form 'lambda: e'; just use the inferred return type.
                return Callable([], [], [], ret_type, self.named_type('builtins.function'))
            else:
                # TODO: Consider reporting an error. However, this is fine if
                # we are just doing the first pass in contextual type
                # inference.
                return AnyType()
        else:
            # Type context available.
            self.chk.check_func_item(e, type_override=inferred_type)
            ret_type = self.chk.type_map[e.expr()]
            return replace_callable_return_type(inferred_type, ret_type)

    def infer_lambda_type_using_context(self, e: FuncExpr) -> Callable:
        """Try to infer lambda expression type using context.

        Return None if could not infer type.
        """
        # TODO also accept 'Any' context
        ctx = self.chk.type_context[-1]
        if not ctx or not isinstance(ctx, Callable):
            return None

        # The context may have function type variables in it. We replace them
        # since these are the type variables we are ultimately trying to infer;
        # they must be considered as indeterminate. We use ErasedType since it
        # does not affect type inference results (it is for purposes like this
        # only).
        ctx = replace_func_type_vars(ctx, ErasedType())

        callable_ctx = cast(Callable, ctx)

        if callable_ctx.arg_kinds != e.arg_kinds:
            # Incompatible context; cannot use it to infer types.
            self.chk.fail(messages.CANNOT_INFER_LAMBDA_TYPE, e)
            return None

        return callable_ctx

    def visit_super_expr(self, e: SuperExpr) -> Type:
        """Type check a super expression (non-lvalue)."""
        t = self.analyse_super(e, False)
        return t

    def analyse_super(self, e: SuperExpr, is_lvalue: bool) -> Type:
        """Type check a super expression."""
        if e.info and e.info.bases:
            # TODO fix multiple inheritance etc
            return analyse_member_access(e.name, self_type(e.info), e,
                                         is_lvalue, True,
                                         self.named_type, self.msg,
                                         e.info.mro[1])
        else:
            # Invalid super. This has been reported by the semantic analyser.
            return AnyType()

    def visit_paren_expr(self, e: ParenExpr) -> Type:
        """Type check a parenthesised expression."""
        return self.accept(e.expr, self.chk.type_context[-1])

    def visit_slice_expr(self, e: SliceExpr) -> Type:
        for index in [e.begin_index, e.end_index, e.stride]:
            if index:
                t = self.accept(index)
                self.chk.check_subtype(t, self.named_type('builtins.int'),
                                       index, messages.INVALID_SLICE_INDEX)
        return self.named_type('builtins.slice')

    def visit_list_comprehension(self, e: ListComprehension) -> Type:
        return self.check_generator_or_comprehension(
            e.generator, 'builtins.list', '<list-comprehension>')

    def visit_generator_expr(self, e: GeneratorExpr) -> Type:
        return self.check_generator_or_comprehension(e, 'typing.Iterator',
                                                     '<generator>')

    def check_generator_or_comprehension(self, gen: GeneratorExpr,
                                         type_name: str,
                                         id_for_messages: str) -> Type:
        """Type check a generator expression or a list comprehension."""

        self.chk.binder.push_frame()
        for index, sequence, conditions in zip(gen.indices, gen.sequences,
                                               gen.condlists):
            sequence_type = self.chk.analyse_iterable_item_type(sequence)
            self.chk.analyse_index_variables(index, sequence_type, gen)
            for condition in conditions:
                self.accept(condition)
        self.chk.binder.pop_frame()

        # Infer the type of the list comprehension by using a synthetic generic
        # callable type.
        tv = TypeVar('T', -1, [], self.chk.object_type())
        constructor = Callable([tv],
                               [nodes.ARG_POS],
                               [None],
                               self.chk.named_generic_type(type_name, [tv]),
                               self.chk.named_type('builtins.function'),
                               id_for_messages,
                               [TypeVarDef('T', -1, None, self.chk.object_type())])
        return self.check_call(constructor,
                               [gen.left_expr], [nodes.ARG_POS], gen)[0]

    def visit_undefined_expr(self, e: UndefinedExpr) -> Type:
        return e.type

    def visit_conditional_expr(self, e: ConditionalExpr) -> Type:
        cond_type = self.accept(e.cond)
        self.check_not_void(cond_type, e)
        if_type = self.accept(e.if_expr)
        else_type = self.accept(e.else_expr, context=if_type)
        return join.join_types(if_type, else_type)

    #
    # Helpers
    #

    def accept(self, node: Node, context: Type = None) -> Type:
        """Type check a node. Alias for TypeChecker.accept."""
        return self.chk.accept(node, context)

    def check_not_void(self, typ: Type, context: Context) -> None:
        """Generate an error if type is Void."""
        self.chk.check_not_void(typ, context)

    def is_boolean(self, typ: Type) -> bool:
        """Is type compatible with bool?"""
        return is_subtype(typ, self.chk.bool_type())

    def named_type(self, name: str) -> Instance:
        """Return an instance type with type given by the name and no type
        arguments. Alias for TypeChecker.named_type.
        """
        return self.chk.named_type(name)

    def is_valid_var_arg(self, typ: Type) -> bool:
        """Is a type valid as a *args argument?"""
        return (isinstance(typ, TupleType) or
                is_subtype(typ, self.chk.named_generic_type('typing.Iterable',
                                                            [AnyType()])) or
                isinstance(typ, AnyType))

    def is_valid_keyword_var_arg(self, typ: Type) -> bool:
        """Is a type valid as a **kwargs argument?"""
        return is_subtype(typ, self.chk.named_generic_type(
            'builtins.dict', [self.named_type('builtins.str'), AnyType()]))

    def has_non_method(self, typ: Type, member: str) -> bool:
        """Does type have a member variable / property with the given name?"""
        if isinstance(typ, Instance):
            return (not typ.type.has_method(member) and
                    typ.type.has_readable_member(member))
        else:
            return False

    def has_member(self, typ: Type, member: str) -> bool:
        """Does type have member with the given name?"""
        # TODO TupleType => also consider tuple attributes
        if isinstance(typ, Instance):
            return typ.type.has_readable_member(member)
        elif isinstance(typ, AnyType):
            return True
        elif isinstance(typ, UnionType):
            result = all(self.has_member(x, member) for x in typ.items)
            return result
        else:
            return False

    def unwrap_list(self, a: List[Node]) -> List[Node]:
        """Unwrap parentheses from a list of expression nodes."""
        r = List[Node]()
        for n in a:
            r.append(self.strip_parens(n))
        return r

    def erase(self, type: Type) -> Type:
        """Replace type variable types in type with Any."""
        return erasetype.erase_type(type)


def is_valid_argc(nargs: int, is_var_arg: bool, callable: Callable) -> bool:
    """Return a boolean indicating whether a call expression has a
    (potentially) compatible number of arguments for calling a function.
    Varargs at caller are not checked.
    """
    if is_var_arg:
        if callable.is_var_arg:
            return True
        else:
            return nargs - 1 <= callable.max_fixed_args()
    elif callable.is_var_arg:
        return nargs >= callable.min_args
    else:
        # Neither has varargs.
        return nargs <= len(callable.arg_types) and nargs >= callable.min_args


def map_actuals_to_formals(caller_kinds: List[int],
                           caller_names: List[str],
                           callee_kinds: List[int],
                           callee_names: List[str],
                           caller_arg_type: Function[[int],
                                                     Type]) -> List[List[int]]:
    """Calculate mapping between actual (caller) args and formals.

    The result contains a list of caller argument indexes mapping to each
    callee argument index, indexed by callee index.

    The caller_arg_type argument should evaluate to the type of the actual
    argument type with the given index.
    """
    ncallee = len(callee_kinds)
    map = [None] * ncallee  # type: List[List[int]]
    for i in range(ncallee):
        map[i] = []
    j = 0
    for i, kind in enumerate(caller_kinds):
        if kind == nodes.ARG_POS:
            if j < ncallee:
                if callee_kinds[j] in [nodes.ARG_POS, nodes.ARG_OPT,
                                       nodes.ARG_NAMED]:
                    map[j].append(i)
                    j += 1
                elif callee_kinds[j] == nodes.ARG_STAR:
                    map[j].append(i)
        elif kind == nodes.ARG_STAR:
            # We need to to know the actual type to map varargs.
            argt = caller_arg_type(i)
            if isinstance(argt, TupleType):
                # A tuple actual maps to a fixed number of formals.
                for k in range(len(argt.items)):
                    if j < ncallee:
                        if callee_kinds[j] != nodes.ARG_STAR2:
                            map[j].append(i)
                        else:
                            raise NotImplementedError()
                        j += 1
            else:
                # Assume that it is an iterable (if it isn't, there will be
                # an error later).
                while j < ncallee:
                    if callee_kinds[j] in (nodes.ARG_NAMED, nodes.ARG_STAR2):
                        break
                    else:
                        map[j].append(i)
                    j += 1
        elif kind == nodes.ARG_NAMED:
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
    return isinstance(t, TupleType) and not cast(TupleType, t).items


def is_duplicate_mapping(mapping: List[int], actual_kinds: List[int]) -> bool:
    # Multiple actuals can map to the same formal only if they both come from
    # varargs (*args and **kwargs); in this case at runtime it is possible that
    # there are no duplicates. We need to allow this, as the convention
    # f(..., *args, **kwargs) is common enough.
    return len(mapping) > 1 and not (
        len(mapping) == 2 and
        actual_kinds[mapping[0]] == nodes.ARG_STAR and
        actual_kinds[mapping[1]] == nodes.ARG_STAR2)


def replace_callable_return_type(c: Callable, new_ret_type: Type) -> Callable:
    """Return a copy of a callable type with a different return type."""
    return Callable(c.arg_types,
                    c.arg_kinds,
                    c.arg_names,
                    new_ret_type,
                    c.fallback,
                    c.name,
                    c.variables,
                    c.bound_vars,
                    c.line)


class ArgInferSecondPassQuery(types.TypeQuery):
    """Query whether an argument type should be inferred in the second pass.

    The result is True if the type has a type variable in a callable return
    type anywhere. For example, the result for Function[[], T] is True if t is
    a type variable.
    """
    def __init__(self) -> None:
        super().__init__(False, types.ANY_TYPE_STRATEGY)

    def visit_callable(self, t: Callable) -> bool:
        return self.query_types(t.arg_types) or t.accept(HasTypeVarQuery())


class HasTypeVarQuery(types.TypeQuery):
    """Visitor for querying whether a type has a type variable component."""
    def __init__(self) -> None:
        super().__init__(False, types.ANY_TYPE_STRATEGY)

    def visit_type_var(self, t: TypeVar) -> bool:
        return True


def has_erased_component(t: Type) -> bool:
    return t is not None and t.accept(HasErasedComponentsQuery())


class HasErasedComponentsQuery(types.TypeQuery):
    """Visitor for querying whether a type has an erased component."""
    def __init__(self) -> None:
        super().__init__(False, types.ANY_TYPE_STRATEGY)

    def visit_erased_type(self, t: ErasedType) -> bool:
        return True
