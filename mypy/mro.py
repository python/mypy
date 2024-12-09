from __future__ import annotations

from typing import Callable

from mypy.nodes import TypeInfo
from mypy.types import Instance, ProperType, TypeVarLikeType
from mypy.typestate import type_state


def calculate_mro(info: TypeInfo, obj_type: Callable[[], Instance] | None = None) -> None:
    """Calculate and set mro (method resolution order).

    Raise MroError if cannot determine mro.
    """
    mro = linearize_hierarchy(info, obj_type)
    assert mro, f"Could not produce a MRO at all for {info}"
    info.mro = mro
    fill_mapped_type_vars(info)
    # The property of falling back to Any is inherited.
    info.fallback_to_any = any(baseinfo.fallback_to_any for baseinfo in info.mro)
    type_state.reset_all_subtype_caches_for(info)


def fill_mapped_type_vars(info: TypeInfo) -> None:
    """Calculates the final TypeVar value from inheritor to parent.

    class A[T1]:
        # mapped_type_vars = {T1: str}

    class B[T2]:
        # mapped_type_vars = {T2: T4}

    class C[T3](B[T3]):
        # mapped_type_vars = {T3: T4}

    class D[T4](C[T4], A[str]):
        # mapped_type_vars = {}
    """
    bases = {b.type: b for b in info.bases}

    for subinfo in filter(lambda x: x.is_generic, info.mro):
        if base_info := bases.get(subinfo):
            subinfo.mapped_type_vars = {
                tv: actual_type for tv, actual_type in zip(subinfo.defn.type_vars, base_info.args)
            }
        info.mapped_type_vars |= subinfo.mapped_type_vars

    final_mapped_type_vars: dict[TypeVarLikeType, ProperType] = {}
    for k, v in info.mapped_type_vars.items():
        final_mapped_type_vars[k] = _resolve_mappped_vars(info.mapped_type_vars, v)

    for subinfo in filter(lambda x: x.is_generic, info.mro):
        _resolve_info_type_vars(subinfo, final_mapped_type_vars)


def _resolve_info_type_vars(
    info: TypeInfo, mapped_type_vars: dict[TypeVarLikeType, ProperType]
) -> None:
    final_mapped_type_vars = {}
    for tv in info.defn.type_vars:
        final_mapped_type_vars[tv] = _resolve_mappped_vars(mapped_type_vars, tv)
    info.mapped_type_vars = final_mapped_type_vars


def _resolve_mappped_vars(
    mapped_type_vars: dict[TypeVarLikeType, ProperType], key: ProperType
) -> ProperType:
    if key in mapped_type_vars:
        return _resolve_mappped_vars(mapped_type_vars, mapped_type_vars[key])
    return key


class MroError(Exception):
    """Raised if a consistent mro cannot be determined for a class."""


def linearize_hierarchy(
    info: TypeInfo, obj_type: Callable[[], Instance] | None = None
) -> list[TypeInfo]:
    # TODO describe
    if info.mro:
        return info.mro
    bases = info.direct_base_classes()
    if not bases and info.fullname != "builtins.object" and obj_type is not None:
        # Probably an error, add a dummy `object` base class,
        # otherwise MRO calculation may spuriously fail.
        bases = [obj_type().type]
    lin_bases = []
    for base in bases:
        assert base is not None, f"Cannot linearize bases for {info.fullname} {bases}"
        lin_bases.append(linearize_hierarchy(base, obj_type))
    lin_bases.append(bases)
    return [info] + merge(lin_bases)


def merge(seqs: list[list[TypeInfo]]) -> list[TypeInfo]:
    seqs = [s.copy() for s in seqs]
    result: list[TypeInfo] = []
    while True:
        seqs = [s for s in seqs if s]
        if not seqs:
            return result
        for seq in seqs:
            head = seq[0]
            if not [s for s in seqs if head in s[1:]]:
                break
        else:
            raise MroError()
        result.append(head)
        for s in seqs:
            if s[0] is head:
                del s[0]
