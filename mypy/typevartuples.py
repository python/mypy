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
    """Partition arguments for a variadic generic with possible defaulted suffix variables.

    Returns: (prefix_args, middle_args, suffix_args, omitted_suffix_vars)
    """
    suffix_vars = type_vars[prefix + 1 :]
    num_req_suffix = sum(not v.has_default() for v in suffix_vars)
    num_opt_suffix = len(suffix_vars) - num_req_suffix

    if len(args) < prefix + num_req_suffix:
        return tuple(args[:prefix]), (), tuple(args[prefix:]), list(suffix_vars)

    opt_args_count = 0
    if num_opt_suffix > 0 and len(args) - prefix > num_req_suffix:
        for _ in range(num_opt_suffix):
            idx = len(args) - 1 - opt_args_count
            if idx < prefix + num_req_suffix:
                break
            candidate = args[idx]
            tv = suffix_vars[len(suffix_vars) - 1 - opt_args_count]
            if isinstance(tv, ParamSpecType) and is_valid_paramspec_arg(candidate):
                opt_args_count += 1
            else:
                break

    prov_suffix_count = num_req_suffix + opt_args_count
    omitted_suffix_vars = list(suffix_vars[prov_suffix_count:])

    prefix_args = tuple(args[:prefix])
    middle_args = tuple(args[prefix : len(args) - prov_suffix_count])
    suffix_args = tuple(args[len(args) - prov_suffix_count :])
    return prefix_args, middle_args, suffix_args, omitted_suffix_vars
