"""Primitive dict ops."""

from typing import List

from mypyc.ir.ops import EmitterInterface, ERR_FALSE, ERR_MAGIC, ERR_NEVER
from mypyc.ir.rtypes import dict_rprimitive, object_rprimitive, bool_rprimitive, int_rprimitive

from mypyc.primitives.registry import (
    name_ref_op, method_op, binary_op, func_op, custom_op,
    simple_emit, negative_int_emit, call_emit, call_negative_bool_emit,
    name_emit,
)


# Get the 'dict' type object.
name_ref_op('builtins.dict',
            result_type=object_rprimitive,
            error_kind=ERR_NEVER,
            emit=name_emit('&PyDict_Type', target_type="PyObject *"),
            is_borrowed=True)

# dict[key]
dict_get_item_op = method_op(
    name='__getitem__',
    arg_types=[dict_rprimitive, object_rprimitive],
    result_type=object_rprimitive,
    error_kind=ERR_MAGIC,
    emit=call_emit('CPyDict_GetItem'))

# dict[key] = value
dict_set_item_op = method_op(
    name='__setitem__',
    arg_types=[dict_rprimitive, object_rprimitive, object_rprimitive],
    result_type=bool_rprimitive,
    error_kind=ERR_FALSE,
    emit=call_negative_bool_emit('CPyDict_SetItem'))

# key in dict
binary_op(op='in',
          arg_types=[object_rprimitive, dict_rprimitive],
          result_type=bool_rprimitive,
          error_kind=ERR_MAGIC,
          format_str='{dest} = {args[0]} in {args[1]} :: dict',
          emit=negative_int_emit('{dest} = PyDict_Contains({args[1]}, {args[0]});'))

# dict1.update(dict2)
dict_update_op = method_op(
    name='update',
    arg_types=[dict_rprimitive, dict_rprimitive],
    result_type=bool_rprimitive,
    error_kind=ERR_FALSE,
    emit=call_negative_bool_emit('CPyDict_Update'),
    priority=2)

# Operation used for **value in dict displays.
# This is mostly like dict.update(obj), but has customized error handling.
dict_update_in_display_op = custom_op(
    arg_types=[dict_rprimitive, dict_rprimitive],
    result_type=bool_rprimitive,
    error_kind=ERR_FALSE,
    emit=call_negative_bool_emit('CPyDict_UpdateInDisplay'),
    format_str='{dest} = {args[0]}.update({args[1]}) (display) :: dict',)

# dict.update(obj)
method_op(
    name='update',
    arg_types=[dict_rprimitive, object_rprimitive],
    result_type=bool_rprimitive,
    error_kind=ERR_FALSE,
    emit=call_negative_bool_emit('CPyDict_UpdateFromAny'))

# dict.get(key, default)
method_op(
    name='get',
    arg_types=[dict_rprimitive, object_rprimitive, object_rprimitive],
    result_type=object_rprimitive,
    error_kind=ERR_MAGIC,
    emit=call_emit('CPyDict_Get'))

# dict.get(key)
method_op(
    name='get',
    arg_types=[dict_rprimitive, object_rprimitive],
    result_type=object_rprimitive,
    error_kind=ERR_MAGIC,
    emit=simple_emit('{dest} = CPyDict_Get({args[0]}, {args[1]}, Py_None);'))


def emit_new_dict(emitter: EmitterInterface, args: List[str], dest: str) -> None:
    if not args:
        emitter.emit_line('%s = PyDict_New();' % (dest,))
        return

    emitter.emit_line('%s = CPyDict_Build(%s, %s);' % (dest, len(args) // 2, ', '.join(args)))


# Construct a dictionary from keys and values.
# Arguments are (key1, value1, ..., keyN, valueN).
new_dict_op = custom_op(
    name='builtins.dict',
    arg_types=[object_rprimitive],
    is_var_arg=True,
    result_type=dict_rprimitive,
    format_str='{dest} = {{{colon_args}}}',
    error_kind=ERR_MAGIC,
    emit=emit_new_dict)

# Construct a dictionary from another dictionary.
func_op(
    name='builtins.dict',
    arg_types=[dict_rprimitive],
    result_type=dict_rprimitive,
    error_kind=ERR_MAGIC,
    emit=call_emit('PyDict_Copy'),
    priority=2)

# Generic one-argument dict constructor: dict(obj)
func_op(
    name='builtins.dict',
    arg_types=[object_rprimitive],
    result_type=dict_rprimitive,
    error_kind=ERR_MAGIC,
    emit=call_emit('CPyDict_FromAny'))


def emit_len(emitter: EmitterInterface, args: List[str], dest: str) -> None:
    temp = emitter.temp_name()
    emitter.emit_declaration('Py_ssize_t %s;' % temp)
    emitter.emit_line('%s = PyDict_Size(%s);' % (temp, args[0]))
    emitter.emit_line('%s = CPyTagged_ShortFromSsize_t(%s);' % (dest, temp))


# len(dict)
func_op(name='builtins.len',
        arg_types=[dict_rprimitive],
        result_type=int_rprimitive,
        error_kind=ERR_NEVER,
        emit=emit_len)
