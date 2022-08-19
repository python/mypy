"""Helpers for interacting with type var tuples."""

from __future__ import annotations

from typing import Sequence, TypeVar

from mypy.types import Instance, ProperType, Type, UnpackType, get_proper_type


def find_unpack_in_list(items: Sequence[Type]) -> int | None:
    unpack_index: int | None = None
    for i, item in enumerate(items):
        proper_item = get_proper_type(item)
        if isinstance(proper_item, UnpackType):
            # We cannot fail here, so we must check this in an earlier
            # semanal phase.
            # Funky code here avoids mypyc narrowing the type of unpack_index.
            old_index = unpack_index
            assert old_index is None
            # Don't return so that we can also sanity check there is only one.
            unpack_index = i
    return unpack_index


T = TypeVar("T")


def split_with_prefix_and_suffix(
    types: tuple[T, ...], prefix: int, suffix: int
) -> tuple[tuple[T, ...], tuple[T, ...], tuple[T, ...]]:
    if suffix:
        return (types[:prefix], types[prefix:-suffix], types[-suffix:])
    else:
        return (types[:prefix], types[prefix:], ())


def split_with_instance(
    typ: Instance,
) -> tuple[tuple[Type, ...], tuple[Type, ...], tuple[Type, ...]]:
    assert typ.type.type_var_tuple_prefix is not None
    assert typ.type.type_var_tuple_suffix is not None
    return split_with_prefix_and_suffix(
        typ.args, typ.type.type_var_tuple_prefix, typ.type.type_var_tuple_suffix
    )


def extract_unpack(types: Sequence[Type]) -> ProperType | None:
    """Given a list of types, extracts either a single type from an unpack, or returns None."""
    if len(types) == 1:
        proper_type = get_proper_type(types[0])
        if isinstance(proper_type, UnpackType):
            return get_proper_type(proper_type.type)
    return None
