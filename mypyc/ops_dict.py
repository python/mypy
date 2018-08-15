"""Primitive dict ops."""

from typing import List

from mypyc.ops import (
    EmitterInterface, PrimitiveOp, dict_rprimitive, object_rprimitive, bool_rprimitive, ERR_FALSE,
    ERR_MAGIC
)
from mypyc.ops_primitive import method_op, binary_op, func_op, simple_emit, negative_int_emit


dict_get_item_op = method_op(
    name='__getitem__',
    arg_types=[dict_rprimitive, object_rprimitive],
    result_type=object_rprimitive,
    error_kind=ERR_MAGIC,
    emit=simple_emit('{dest} = CPyDict_GetItem({args[0]}, {args[1]});'))


dict_set_item_op = method_op(
    name='__setitem__',
    arg_types=[dict_rprimitive, object_rprimitive, object_rprimitive],
    result_type=bool_rprimitive,
    error_kind=ERR_FALSE,
    emit=simple_emit('{dest} = CPyDict_SetItem({args[0]}, {args[1]}, {args[2]}) >= 0;'))


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
    emit=simple_emit('{dest} = CPyDict_Update({args[0]}, {args[1]}) != -1;'),
    priority=2)

method_op(
    name='update',
    arg_types=[dict_rprimitive, object_rprimitive],
    result_type=bool_rprimitive,
    error_kind=ERR_FALSE,
    emit=simple_emit('{dest} = CPyDict_UpdateFromSeq({args[0]}, {args[1]}) != -1;'))

new_dict_op = func_op(
    name='builtins.dict',
    arg_types=[],
    result_type=dict_rprimitive,
    error_kind=ERR_MAGIC,
    format_str='{dest} = {{}}',
    emit=simple_emit('{dest} = PyDict_New();'))
