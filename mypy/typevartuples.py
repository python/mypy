"""Helpers for interacting with type var tuples."""

from __future__ import annotations

from collections.abc import Sequence

from mypy.types import (
    AnyType,
    Instance,
    Parameters,
    ParamSpecType,
    Type,
    TypeVarLikeType,
    TypeVarTupleType,
    UnboundType,
    UnpackType,
    get_proper_type,
    split_with_prefix_and_suffix,
)


def split_with_instance(
    typ: Instance,
) -> tuple[tuple[Type, ...], tuple[Type, ...], tuple[Type, ...]]:
    assert typ.type.type_var_tuple_prefix is not None
    assert typ.type.type_var_tuple_suffix is not None
    return split_with_prefix_and_suffix(
        typ.args, typ.type.type_var_tuple_prefix, typ.type.type_var_tuple_suffix
    )


def erased_vars(type_vars: Sequence[TypeVarLikeType], type_of_any: int) -> list[Type]:
    args: list[Type] = []
    for tv in type_vars:
        # Valid erasure for *Ts is *tuple[Any, ...], not just Any.
        if isinstance(tv, TypeVarTupleType):
            args.append(UnpackType(tv.tuple_fallback.copy_modified(args=[AnyType(type_of_any)])))
        else:
            args.append(AnyType(type_of_any))
    return args


def is_valid_paramspec_arg(arg: Type) -> bool:
    proper = get_proper_type(arg)
    return isinstance(proper, (Parameters, ParamSpecType, AnyType, UnboundType))


def split_variadic_args_with_defaults(
    type_vars: Sequence[TypeVarLikeType], prefix: int, args: Sequence[Type]
) -> tuple[tuple[Type, ...], tuple[Type, ...], tuple[Type, ...], list[TypeVarLikeType]]:
    """Split type arguments for a generic that has a TypeVarTuple.

    Like split_with_prefix_and_suffix, but takes into account defaulted suffix
    type variables that may be omitted. A defaulted ParamSpec suffix is only
    consumed if the trailing argument is a valid ParamSpec argument.
    """
    suffix_vars = list(type_vars[prefix + 1 :])
    suffix = len(suffix_vars)
    if suffix == 0:
        return tuple(args[:prefix]), tuple(args[prefix:]), (), []

    num_required_suffix = sum(not tv.has_default() for tv in suffix_vars)
    num_optional_suffix = suffix - num_required_suffix

    # Not enough args to satisfy prefix + required suffix.
    if len(args) < prefix + num_required_suffix:
        return tuple(args[:prefix]), (), tuple(args[prefix:]), suffix_vars

    opt_consumed = 0
    if num_optional_suffix > 0 and len(args) - prefix > num_required_suffix:
        # Try to consume optional suffix args from the right when they look like
        # valid arguments for those suffix variables.
        for i in range(num_optional_suffix):
            idx = len(args) - 1 - opt_consumed
            if idx < prefix + num_required_suffix:
                break
            candidate = args[idx]
            tv = suffix_vars[suffix - 1 - opt_consumed]
            if isinstance(tv, ParamSpecType) and is_valid_paramspec_arg(candidate):
                opt_consumed += 1
            elif isinstance(tv, ParamSpecType):
                # Not a valid ParamSpec arg: leave it for the TypeVarTuple.
                break
            else:
                # For non-ParamSpec suffix vars we keep the conservative split.
                break

    provided_suffix = num_required_suffix + opt_consumed
    omitted_suffix_vars = suffix_vars[provided_suffix:]

    prefix_args = tuple(args[:prefix])
    middle_args = (
        tuple(args[prefix : len(args) - provided_suffix])
        if provided_suffix
        else tuple(args[prefix:])
    )
    suffix_args = tuple(args[len(args) - provided_suffix :]) if provided_suffix else ()
    return prefix_args, middle_args, suffix_args, omitted_suffix_vars
