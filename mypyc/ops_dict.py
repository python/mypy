"""Primitive dict ops."""

from typing import List

from mypyc.ops import (
    EmitterInterface,
    dict_rprimitive, object_rprimitive, bool_rprimitive, int_rprimitive,
    ERR_FALSE, ERR_MAGIC, ERR_NEVER,
)
from mypyc.ops_primitive import (
    name_ref_op, method_op, binary_op, func_op, custom_op,
    simple_emit, negative_int_emit, call_emit, call_negative_bool_emit,
)


name_ref_op('builtins.dict',
            result_type=object_rprimitive,
            error_kind=ERR_NEVER,
            emit=simple_emit('{dest} = (PyObject *)&PyDict_Type;'),
            is_borrowed=True)

dict_get_item_op = method_op(
    name='__getitem__',
    arg_types=[dict_rprimitive, object_rprimitive],
    result_type=object_rprimitive,
    error_kind=ERR_MAGIC,
    emit=call_emit('CPyDict_GetItem'))


dict_set_item_op = method_op(
    name='__setitem__',
    arg_types=[dict_rprimitive, object_rprimitive, object_rprimitive],
    result_type=bool_rprimitive,
    error_kind=ERR_FALSE,
    emit=call_negative_bool_emit('CPyDict_SetItem'))


binary_op(op='in',
          arg_types=[object_rprimitive, dict_rprimitive],
          result_type=bool_rprimitive,
          error_kind=ERR_MAGIC,
          format_str='{dest} = {args[0]} in {args[1]} :: dict',
          emit=negative_int_emit('{dest} = PyDict_Contains({args[1]}, {args[0]});'))

dict_update_op = method_op(
    name='update',
    arg_types=[dict_rprimitive, dict_rprimitive],
    result_type=bool_rprimitive,
    error_kind=ERR_FALSE,
    emit=call_negative_bool_emit('CPyDict_Update'),
    priority=2)

dict_update_in_display_op = custom_op(
    arg_types=[dict_rprimitive, dict_rprimitive],
    result_type=bool_rprimitive,
    error_kind=ERR_FALSE,
    emit=call_negative_bool_emit('CPyDict_UpdateInDisplay'),
    format_str='{dest} = {args[0]}.update({args[1]}) (display) :: dict',)

method_op(
    name='update',
    arg_types=[dict_rprimitive, object_rprimitive],
    result_type=bool_rprimitive,
    error_kind=ERR_FALSE,
    emit=simple_emit('{dest} = CPyDict_UpdateFromAny({args[0]}, {args[1]}) != -1;'))

method_op(
    name='get',
    arg_types=[dict_rprimitive, object_rprimitive, object_rprimitive],
    result_type=object_rprimitive,
    error_kind=ERR_MAGIC,
    emit=call_emit('CPyDict_Get'))

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


new_dict_op = custom_op(
    name='builtins.dict',
    arg_types=[object_rprimitive],
    is_var_arg=True,
    result_type=dict_rprimitive,
    format_str='{dest} = {{{colon_args}}}',
    error_kind=ERR_MAGIC,
    emit=emit_new_dict)

func_op(
    name='builtins.dict',
    arg_types=[dict_rprimitive],
    result_type=dict_rprimitive,
    error_kind=ERR_MAGIC,
    emit=call_emit('PyDict_Copy'),
    priority=2)

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


func_op(name='builtins.len',
        arg_types=[dict_rprimitive],
        result_type=int_rprimitive,
        error_kind=ERR_NEVER,
        emit=emit_len)
