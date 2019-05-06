"""Primitive tuple ops.

These are for varying-length tuples represented as Python tuple objects
(RPrimitive, not RTuple).
"""

from typing import List

from mypyc.ops import (
    EmitterInterface, PrimitiveOp, tuple_rprimitive, int_rprimitive, list_rprimitive,
    object_rprimitive, ERR_NEVER, ERR_MAGIC
)
from mypyc.ops_primitive import (
    func_op, method_op, call_emit,
)


tuple_get_item_op = method_op(
    name='__getitem__',
    arg_types=[tuple_rprimitive, int_rprimitive],
    result_type=object_rprimitive,
    error_kind=ERR_MAGIC,
    emit=call_emit('CPySequenceTuple_GetItem'))


def emit_len(emitter: EmitterInterface, args: List[str], dest: str) -> None:
    temp = emitter.temp_name()
    emitter.emit_declaration('Py_ssize_t %s;' % temp)
    emitter.emit_line('%s = PyTuple_GET_SIZE(%s);' % (temp, args[0]))
    emitter.emit_line('%s = CPyTagged_ShortFromSsize_t(%s);' % (dest, temp))


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
    emit=call_emit('PyList_AsTuple'),
    priority=2)

func_op(
    name='builtins.tuple',
    arg_types=[object_rprimitive],
    result_type=tuple_rprimitive,
    error_kind=ERR_MAGIC,
    emit=call_emit('PySequence_Tuple'))
