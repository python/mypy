"""Primitive tuple ops.

These are for varying-length tuples represented as Python tuple objects
(RPrimitive, not RTuple).
"""

from typing import List

from mypyc.ops import (
    EmitterInterface, PrimitiveOp, tuple_rprimitive, int_rprimitive, list_rprimitive,
    object_rprimitive, ERR_NEVER, ERR_MAGIC
)
from mypyc.ops_primitive import method_op, func_op, simple_emit


tuple_get_item_op = method_op(
    name='__getitem__',
    arg_types=[tuple_rprimitive, int_rprimitive],
    result_type=object_rprimitive,
    error_kind=ERR_MAGIC,
    emit=simple_emit('{dest} = CPySequenceTuple_GetItem({args[0]}, {args[1]});'))


def emit_len(emitter: EmitterInterface, args: List[str], dest: str) -> None:
    temp = emitter.temp_name()
    emitter.emit_declaration('long long %s;' % temp)
    emitter.emit_line('%s = PyTuple_GET_SIZE(%s);' % (temp, args[0]))
    emitter.emit_line('%s = CPyTagged_ShortFromLongLong(%s);' % (dest, temp))


tuple_len_op = func_op(
    name='builtins.len',
    arg_types=[tuple_rprimitive],
    result_type=int_rprimitive,
    error_kind=ERR_NEVER,
    emit=emit_len)


list_tuple_op = func_op(
    name='builtins.tuple',
    arg_types=[list_rprimitive],
    result_type=tuple_rprimitive,
    error_kind=ERR_MAGIC,
    emit=simple_emit('{dest} = PyList_AsTuple({args[0]});'))
