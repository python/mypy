"""Alore code generation for runtime type operations (OBSOLETE)."""

from nodes import MypyFile, TypeDef, TypeInfo
from types import Instance, TypeVar, BOUND_VAR, Type
import transform
from maptypevar import num_slots, get_tvar_access_path
from compileslotmap import compile_slot_mapping
from transutil import dynamic_suffix, tvar_slot_name


str generate_runtime_support(MypyFile f):
    return generate_slot_map(f) + '\n' + generate_type_map(f)


# Type-to-slot mapping


str generate_slot_map(MypyFile f):
    str[] map = []
    str[] ops = []
    map.append('def __InitSlotMap()')
    map.append('  __SlotMap = std::Map(')
    for d in f.defs:
        if isinstance(d, TypeDef):
            td = (TypeDef)d
            if td.info:
                add_slot_map_data(map, ops, td.info)
    map.append('  )')
    map.append('end')
    return '\n'.join(map) + '\n' + '\n'.join(ops)


void add_slot_map_data(str[] map, str[] ops, TypeInfo typ):
    base = typ
    while base:
        add_slot_map_support_for_type_pair(map, ops, base, typ)
        base = base.base


void add_slot_map_support_for_type_pair(str[] map, str[] ops, TypeInfo base,
                                        TypeInfo typ):
    op = '__{}TypeTo{}Slots'.format(base.name(), typ.name())
    map.append('    ({}, {}) : {},'.format(base.name(), typ.name(), op))
    if typ.is_generic():
        map.append('    ({}, {}) : {},'.format(base.name(), typ.name() +
                                               dynamic_suffix(False),
                                               op))
    generate_slot_map_op(ops, op, base, typ)


void generate_slot_map_op(str[] ops, str op, TypeInfo base, TypeInfo typ):
    ops.append('def {}(t)'.format(op))
    nslots = num_slots(typ)
    slots = compile_slot_mapping(base)
    a = <str> []
    for t in slots:
        a.append(transform_type_to_runtime_repr(t))
    for i in range(len(slots), nslots):
        a.append('__Dyn')
    ops.append('  return [' + ', '.join(a) + ']')
    ops.append('end')


str transform_type_to_runtime_repr(Type t):
    if isinstance(t, Instance):
        inst = (Instance)t
        if inst.args == []:
            return inst.type.name()
        else:
            args = <str> []
            for a in inst.args:
                args.append(transform_type_to_runtime_repr(a))
            return '__Gen({}, [{}])'.format(inst.type.name(), ', '.join(args))
    elif isinstance(t, TypeVar):
        tv = (TypeVar)t
        return 't.args[{}]'.format(tv.id - 1)
    else:
        raise TypeError('{} not supported'.format(t))


# Slot-to-type mapping


str generate_type_map(MypyFile f):
    str[] map = []
    str[] ops = []
    map.append('def __InitTypeMap()')
    for alt, suffix in [(None, ''), (BOUND_VAR, 'B')]:
        map.append('  __TypeMap{} = std::Map('.format(suffix))
        for d in f.defs:
            if isinstance(d, TypeDef):
                td = (TypeDef)d
                if td.info is not None:
                    add_type_map_support_for_type(map, ops, td.info, alt,
                                                  suffix)
        map.append('  )')
    map.append('end')
    return '\n'.join(map) + '\n' + '\n'.join(ops)


void add_type_map_support_for_type(str[] map, str[] ops, TypeInfo typ, alt,
                                   str suffix):
    op = '__{}ValueToType{}'.format(typ.name(), suffix)
    map.append('    {} : {},'.format(typ.name(), op))
    if typ.is_generic():
        map.append('    {} : {},'.format(typ.name() + dynamic_suffix(False),
                                         op))
    generate_type_map_op(ops, op, typ, alt)


void generate_type_map_op(str[] ops, str op, typ, alt):
    ops.append('def {}(v)'.format(op))
    a = <str> []
    for i in range(len(typ.type_vars)):
        p = get_tvar_access_path(typ, i + 1)
        expr = 'v.' + tvar_slot_name(p[0] - 1, alt)
        for j in p[1:]:
            expr += '.args[{}]'.format(j - 1)
        a.append(expr)
    ops.append('  return [{}]'.format(', '.join(a)))
    ops.append('end')
