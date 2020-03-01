"""Primitive set ops."""
from mypyc.ops_primitive import (
    func_op, method_op, binary_op,
    simple_emit, negative_int_emit, call_emit, call_negative_bool_emit,
)
from mypyc.ops import (
    object_rprimitive, bool_rprimitive, set_rprimitive, int_rprimitive, ERR_MAGIC, ERR_FALSE,
    ERR_NEVER, EmitterInterface
)
from typing import List


new_set_op = func_op(
    name='builtins.set',
    arg_types=[],
    result_type=set_rprimitive,
    error_kind=ERR_MAGIC,
    emit=simple_emit('{dest} = PySet_New(NULL);')
)

func_op(
    name='builtins.set',
    arg_types=[object_rprimitive],
    result_type=set_rprimitive,
    error_kind=ERR_MAGIC,
    emit=call_emit('PySet_New')
)

func_op(
    name='builtins.frozenset',
    arg_types=[object_rprimitive],
    result_type=object_rprimitive,
    error_kind=ERR_MAGIC,
    emit=call_emit('PyFrozenSet_New')
)


def emit_len(emitter: EmitterInterface, args: List[str], dest: str) -> None:
    temp = emitter.temp_name()
    emitter.emit_declaration('Py_ssize_t %s;' % temp)
    emitter.emit_line('%s = PySet_GET_SIZE(%s);' % (temp, args[0]))
    emitter.emit_line('%s = CPyTagged_ShortFromSsize_t(%s);' % (dest, temp))


func_op(
    name='builtins.len',
    arg_types=[set_rprimitive],
    result_type=int_rprimitive,
    error_kind=ERR_NEVER,
    emit=emit_len,
)


binary_op(
    op='in',
    arg_types=[object_rprimitive, set_rprimitive],
    result_type=bool_rprimitive,
    error_kind=ERR_MAGIC,
    format_str='{dest} = {args[0]} in {args[1]} :: set',
    emit=negative_int_emit('{dest} = PySet_Contains({args[1]}, {args[0]});')
)


method_op(
    name='remove',
    arg_types=[set_rprimitive, object_rprimitive],
    result_type=bool_rprimitive,
    error_kind=ERR_FALSE,
    emit=call_emit('CPySet_Remove')
)


method_op(
    name='discard',
    arg_types=[set_rprimitive, object_rprimitive],
    result_type=bool_rprimitive,
    error_kind=ERR_FALSE,
    emit=call_negative_bool_emit('PySet_Discard')
)


set_add_op = method_op(
    name='add',
    arg_types=[set_rprimitive, object_rprimitive],
    result_type=bool_rprimitive,
    error_kind=ERR_FALSE,
    emit=call_negative_bool_emit('PySet_Add')
)


# This is not a public API but looks like it should be fine.
set_update_op = method_op(
    name='update',
    arg_types=[set_rprimitive, object_rprimitive],
    result_type=bool_rprimitive,
    error_kind=ERR_FALSE,
    emit=call_negative_bool_emit('_PySet_Update')
)


method_op(
    name='clear',
    arg_types=[set_rprimitive],
    result_type=bool_rprimitive,
    error_kind=ERR_FALSE,
    emit=call_negative_bool_emit('PySet_Clear')
)


method_op(
    name='pop',
    arg_types=[set_rprimitive],
    result_type=object_rprimitive,
    error_kind=ERR_MAGIC,
    emit=call_emit('PySet_Pop')
)
