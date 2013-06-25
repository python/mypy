"""Alore code generation for runtime type operations (OBSOLETE)."""

from nodes import MypyFile, TypeDef, TypeInfo
from types import Instance, TypeVar, BOUND_VAR, Type
import transform
from maptypevar import num_slots, get_tvar_access_path
from compileslotmap import compile_slot_mapping
from transutil import dynamic_suffix, tvar_slot_name
from typing import List, cast


def generate_runtime_support(f: MypyFile) -> str:
    return generate_slot_map(f) + '\n' + generate_type_map(f)


# Type-to-slot mapping


def generate_slot_map(f: MypyFile) -> str:
    map = [] # type: List[str]
    ops = [] # type: List[str]
    map.append('def __InitSlotMap()')
    map.append('  __SlotMap = std::Map(')
    for d in f.defs:
        if isinstance(d, TypeDef):
            td = cast(TypeDef, d)
            if td.info:
                add_slot_map_data(map, ops, td.info)
    map.append('  )')
    map.append('end')
    return '\n'.join(map) + '\n' + '\n'.join(ops)


def add_slot_map_data(map: List[str], ops: List[str], typ: TypeInfo) -> None:
    base = typ
    while base:
        add_slot_map_support_for_type_pair(map, ops, base, typ)
        base = base.base


def add_slot_map_support_for_type_pair(map: List[str], ops: List[str], base: TypeInfo,
                                        typ: TypeInfo) -> None:
    op = '__{}TypeTo{}Slots'.format(base.name(), typ.name())
    map.append('    ({}, {}) : {},'.format(base.name(), typ.name(), op))
    if typ.is_generic():
        map.append('    ({}, {}) : {},'.format(base.name(), typ.name() +
                                               dynamic_suffix(False),
                                               op))
    generate_slot_map_op(ops, op, base, typ)


def generate_slot_map_op(ops: List[str], op: str, base: TypeInfo, typ: TypeInfo) -> None:
    ops.append('def {}(t)'.format(op))
    nslots = num_slots(typ)
    slots = compile_slot_mapping(base)
    a = [] # type: List[str]
    for t in slots:
        a.append(transform_type_to_runtime_repr(t))
    for i in range(len(slots), nslots):
        a.append('__Dyn')
    ops.append('  return [' + ', '.join(a) + ']')
    ops.append('end')


def transform_type_to_runtime_repr(t: Type) -> str:
    if isinstance(t, Instance):
        inst = cast(Instance, t)
        if inst.args == []:
            return inst.type.name()
        else:
            args = [] # type: List[str]
            for a in inst.args:
                args.append(transform_type_to_runtime_repr(a))
            return '__Gen({}, [{}])'.format(inst.type.name(), ', '.join(args))
    elif isinstance(t, TypeVar):
        tv = cast(TypeVar, t)
        return 't.args[{}]'.format(tv.id - 1)
    else:
        raise TypeError('{} not supported'.format(t))


# Slot-to-type mapping


def generate_type_map(f: MypyFile) -> str:
    map = [] # type: List[str]
    ops = [] # type: List[str]
    map.append('def __InitTypeMap()')
    for alt, suffix in [(None, ''), (BOUND_VAR, 'B')]:
        map.append('  __TypeMap{} = std::Map('.format(suffix))
        for d in f.defs:
            if isinstance(d, TypeDef):
                td = cast(TypeDef, d)
                if td.info is not None:
                    add_type_map_support_for_type(map, ops, td.info, alt,
                                                  suffix)
        map.append('  )')
    map.append('end')
    return '\n'.join(map) + '\n' + '\n'.join(ops)


def add_type_map_support_for_type(map: List[str], ops: List[str], typ: TypeInfo, alt,
                                   suffix: str) -> None:
    op = '__{}ValueToType{}'.format(typ.name(), suffix)
    map.append('    {} : {},'.format(typ.name(), op))
    if typ.is_generic():
        map.append('    {} : {},'.format(typ.name() + dynamic_suffix(False),
                                         op))
    generate_type_map_op(ops, op, typ, alt)


def generate_type_map_op(ops: List[str], op: str, typ, alt) -> None:
    ops.append('def {}(v)'.format(op))
    a = [] # type: List[str]
    for i in range(len(typ.type_vars)):
        p = get_tvar_access_path(typ, i + 1)
        expr = 'v.' + tvar_slot_name(p[0] - 1, alt)
        for j in p[1:]:
            expr += '.args[{}]'.format(j - 1)
        a.append(expr)
    ops.append('  return [{}]'.format(', '.join(a)))
    ops.append('end')
