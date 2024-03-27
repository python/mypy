"""Plugin for supporting the functools standard library module."""

from __future__ import annotations

from typing import Final, NamedTuple

import mypy.checker
import mypy.plugin
from mypy.argmap import map_actuals_to_formals
from mypy.nodes import ARG_POS, ARG_STAR2, ArgKind, Argument, FuncItem, Var
from mypy.plugins.common import add_method_to_class
from mypy.types import (
    AnyType,
    CallableType,
    Instance,
    Overloaded,
    Type,
    TypeOfAny,
    UnboundType,
    UninhabitedType,
    get_proper_type,
)

functools_total_ordering_makers: Final = {"functools.total_ordering"}

_ORDERING_METHODS: Final = {"__lt__", "__le__", "__gt__", "__ge__"}


class _MethodInfo(NamedTuple):
    is_static: bool
    type: CallableType


def functools_total_ordering_maker_callback(
    ctx: mypy.plugin.ClassDefContext, auto_attribs_default: bool = False
) -> bool:
    """Add dunder methods to classes decorated with functools.total_ordering."""
    comparison_methods = _analyze_class(ctx)
    if not comparison_methods:
        ctx.api.fail(
            'No ordering operation defined when using "functools.total_ordering": < > <= >=',
            ctx.reason,
        )
        return True

    # prefer __lt__ to __le__ to __gt__ to __ge__
    root = max(comparison_methods, key=lambda k: (comparison_methods[k] is None, k))
    root_method = comparison_methods[root]
    if not root_method:
        # None of the defined comparison methods can be analysed
        return True

    other_type = _find_other_type(root_method)
    bool_type = ctx.api.named_type("builtins.bool")
    ret_type: Type = bool_type
    if root_method.type.ret_type != ctx.api.named_type("builtins.bool"):
        proper_ret_type = get_proper_type(root_method.type.ret_type)
        if not (
            isinstance(proper_ret_type, UnboundType)
            and proper_ret_type.name.split(".")[-1] == "bool"
        ):
            ret_type = AnyType(TypeOfAny.implementation_artifact)
    for additional_op in _ORDERING_METHODS:
        # Either the method is not implemented
        # or has an unknown signature that we can now extrapolate.
        if not comparison_methods.get(additional_op):
            args = [Argument(Var("other", other_type), other_type, None, ARG_POS)]
            add_method_to_class(ctx.api, ctx.cls, additional_op, args, ret_type)

    return True


def _find_other_type(method: _MethodInfo) -> Type:
    """Find the type of the ``other`` argument in a comparison method."""
    first_arg_pos = 0 if method.is_static else 1
    cur_pos_arg = 0
    other_arg = None
    for arg_kind, arg_type in zip(method.type.arg_kinds, method.type.arg_types):
        if arg_kind.is_positional():
            if cur_pos_arg == first_arg_pos:
                other_arg = arg_type
                break

            cur_pos_arg += 1
        elif arg_kind != ARG_STAR2:
            other_arg = arg_type
            break

    if other_arg is None:
        return AnyType(TypeOfAny.implementation_artifact)

    return other_arg


def _analyze_class(ctx: mypy.plugin.ClassDefContext) -> dict[str, _MethodInfo | None]:
    """Analyze the class body, its parents, and return the comparison methods found."""
    # Traverse the MRO and collect ordering methods.
    comparison_methods: dict[str, _MethodInfo | None] = {}
    # Skip object because total_ordering does not use methods from object
    for cls in ctx.cls.info.mro[:-1]:
        for name in _ORDERING_METHODS:
            if name in cls.names and name not in comparison_methods:
                node = cls.names[name].node
                if isinstance(node, FuncItem) and isinstance(node.type, CallableType):
                    comparison_methods[name] = _MethodInfo(node.is_static, node.type)
                    continue

                if isinstance(node, Var):
                    proper_type = get_proper_type(node.type)
                    if isinstance(proper_type, CallableType):
                        comparison_methods[name] = _MethodInfo(node.is_staticmethod, proper_type)
                        continue

                comparison_methods[name] = None

    return comparison_methods


def partial_new_callback(ctx: mypy.plugin.FunctionContext) -> Type:
    """Infer a more precise return type for functools.partial"""
    if not isinstance(ctx.api, mypy.checker.TypeChecker):  # use internals
        return ctx.default_return_type
    if len(ctx.arg_types) != 3:  # fn, *args, **kwargs
        return ctx.default_return_type
    if len(ctx.arg_types[0]) != 1:
        return ctx.default_return_type

    if isinstance(get_proper_type(ctx.arg_types[0][0]), Overloaded):
        # TODO: handle overloads, just fall back to whatever the non-plugin code does
        return ctx.default_return_type
    fn_type = ctx.api.extract_callable_type(ctx.arg_types[0][0], ctx=ctx.default_return_type)
    if fn_type is None:
        return ctx.default_return_type

    defaulted = fn_type.copy_modified(
        arg_kinds=[
            (
                ArgKind.ARG_OPT
                if k == ArgKind.ARG_POS
                else (ArgKind.ARG_NAMED_OPT if k == ArgKind.ARG_NAMED else k)
            )
            for k in fn_type.arg_kinds
        ]
    )
    if defaulted.line < 0:
        # Make up a line number if we don't have one
        defaulted.set_line(ctx.default_return_type)

    actual_args = [a for param in ctx.args[1:] for a in param]
    actual_arg_kinds = [a for param in ctx.arg_kinds[1:] for a in param]
    actual_arg_names = [a for param in ctx.arg_names[1:] for a in param]
    actual_types = [a for param in ctx.arg_types[1:] for a in param]

    _, bound = ctx.api.expr_checker.check_call(
        callee=defaulted,
        args=actual_args,
        arg_kinds=actual_arg_kinds,
        arg_names=actual_arg_names,
        context=defaulted,
    )
    bound = get_proper_type(bound)
    if not isinstance(bound, CallableType):
        return ctx.default_return_type

    formal_to_actual = map_actuals_to_formals(
        actual_kinds=actual_arg_kinds,
        actual_names=actual_arg_names,
        formal_kinds=fn_type.arg_kinds,
        formal_names=fn_type.arg_names,
        actual_arg_type=lambda i: actual_types[i],
    )

    partial_kinds = []
    partial_types = []
    partial_names = []
    # We need to fully apply any positional arguments (they cannot be respecified)
    # However, keyword arguments can be respecified, so just give them a default
    for i, actuals in enumerate(formal_to_actual):
        if len(bound.arg_types) == len(fn_type.arg_types):
            arg_type = bound.arg_types[i]
            if isinstance(get_proper_type(arg_type), UninhabitedType):
                arg_type = fn_type.arg_types[i]  # bit of a hack
        else:
            # TODO: I assume that bound and fn_type have the same arguments. It appears this isn't
            # true when PEP 646 things are happening. See testFunctoolsPartialTypeVarTuple
            arg_type = fn_type.arg_types[i]

        if not actuals or fn_type.arg_kinds[i] in (ArgKind.ARG_STAR, ArgKind.ARG_STAR2):
            partial_kinds.append(fn_type.arg_kinds[i])
            partial_types.append(arg_type)
            partial_names.append(fn_type.arg_names[i])
        elif actuals:
            if any(actual_arg_kinds[j] == ArgKind.ARG_POS for j in actuals):
                continue
            kind = actual_arg_kinds[actuals[0]]
            if kind == ArgKind.ARG_NAMED:
                kind = ArgKind.ARG_NAMED_OPT
            partial_kinds.append(kind)
            partial_types.append(arg_type)
            partial_names.append(fn_type.arg_names[i])

    ret_type = bound.ret_type
    if isinstance(get_proper_type(ret_type), UninhabitedType):
        ret_type = fn_type.ret_type  # same kind of hack as above

    partially_applied = fn_type.copy_modified(
        arg_types=partial_types,
        arg_kinds=partial_kinds,
        arg_names=partial_names,
        ret_type=ret_type,
    )

    ret = ctx.api.named_generic_type("functools.partial", [ret_type])
    ret = ret.copy_with_extra_attr("__mypy_partial", partially_applied)
    return ret


def partial_call_callback(ctx: mypy.plugin.MethodContext) -> Type:
    """Infer a more precise return type for functools.partial.__call__."""
    if (
        not isinstance(ctx.api, mypy.checker.TypeChecker)  # use internals
        or not isinstance(ctx.type, Instance)
        or ctx.type.type.fullname != "functools.partial"
        or not ctx.type.extra_attrs
        or "__mypy_partial" not in ctx.type.extra_attrs.attrs
    ):
        return ctx.default_return_type

    partial_type = ctx.type.extra_attrs.attrs["__mypy_partial"]
    if len(ctx.arg_types) != 2:  # *args, **kwargs
        return ctx.default_return_type

    args = [a for param in ctx.args for a in param]
    arg_kinds = [a for param in ctx.arg_kinds for a in param]
    arg_names = [a for param in ctx.arg_names for a in param]

    result = ctx.api.expr_checker.check_call(
        callee=partial_type,
        args=args,
        arg_kinds=arg_kinds,
        arg_names=arg_names,
        context=ctx.context,
    )
    return result[0]
