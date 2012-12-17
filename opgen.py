from nodes import MypyFile, TypeDef
from mtypes import Instance, TypeVar, BOUND_VAR
import transform
from maptypevar2 import num_slots, get_tvar_access_path
from compileslotmap import compile_slot_mapping
from transutil import dynamic_suffix, tvar_slot_name


str generate_runtime_support(MypyFile f):
    return generate_slot_map(f) + '\n' + generate_type_map(f)


# Type-to-slot mapping


str generate_slot_map(MypyFile f):
    list<str> map = []
    list<str> ops = []
    map.append('def __InitSlotMap()')
    map.append('  __SlotMap = std::Map(')
    for d in f.defs:
        if isinstance(d, TypeDef):
            td = (TypeDef)d
            if td.info is not None:
                add_slot_map_data(map, ops, td.info)
    map.append('  )')
    map.append('end')
    return '\n'.join(map) + '\n' + '\n'.join(ops)


def add_slot_map_data(map, ops, typ):
    base = typ
    while base is not None:
        add_slot_map_support_for_type_pair(map, ops, base, typ)
        base = base.base


def add_slot_map_support_for_type_pair(map, ops, base, typ):
    op = '__{}TypeTo{}Slots'.format(base.name, typ.name)
    map.append('    ({}, {}) : {},'.format(base.name, typ.name, op))
    if typ.is_generic:
        map.append('    ({}, {}) : {},'.format(base.name, typ.name +
                                               dynamic_suffix(False),
                                               op))
    generate_slot_map_op(ops, op, base, typ)


def generate_slot_map_op(ops, op, base, typ):
    ops.append('def {}(t)'.format(op))
    nslots = num_slots(typ)
    slots = compile_slot_mapping(base)
    a = []
    for t in slots:
        a.append(transform_type_to_runtime_repr(t))
    for i in range(len(slots), nslots):
        a.append('__Dyn')
    ops.append('  return [' + ', '.join(a) + ']')
    ops.append('end')


def transform_type_to_runtime_repr(t):
    if isinstance(t, Instance):
        if t.args == []:
            return t.typ.name
        else:
            args = []
            for a in t.args:
                args.append(transform_type_to_runtime_repr(a))
            return '__Gen({}, [{}])'.format(t.typ.name, ', '.join(args))
    elif isinstance(t, TypeVar):
        return 't.args[{}]'.format(t.id - 1)
    else:
        raise TypeError('{} not supported'.format(t))


# Slot-to-type mapping


str generate_type_map(MypyFile f):
    list<str> map = []
    list<str> ops = []
    map.append('def __InitTypeMap()')
    for alt, suffix in [(None, ''), (BOUND_VAR, 'B')]:
        map.append('  __TypeMap{} = std::Map('.format(suffix))
        for d in f.defs:
            if isinstance(d, TypeDef):
                td = (TypeDef)d
                if td.info is not None:
                    add_type_map_support_for_type(map, ops, td.info, alt, suffix)
        map.append('  )')
    map.append('end')
    return '\n'.join(map) + '\n' + '\n'.join(ops)


def add_type_map_support_for_type(map, ops, typ, alt, suffix):
    op = '__{}ValueToType{}'.format(typ.name, suffix)
    map.append('    {} : {},'.format(typ.name, op))
    if typ.is_generic:
        map.append('    {} : {},'.format(typ.name + dynamic_suffix(False), op))
    generate_type_map_op(ops, op, typ, alt)


def generate_type_map_op(ops, op, typ, alt):
    ops.append('def {}(v)'.format(op))
    a = []
    for i in range(len(typ.type_vars)):
        p = get_tvar_access_path(typ, i + 1)
        expr = 'v.' + tvar_slot_name(p[0] - 1, alt)
        for j in p[1:]:
            expr += '.args[{}]'.format(j - 1)
        a.append(expr)
    ops.append('  return [{}]'.format(', '.join(a)))
    ops.append('end')
