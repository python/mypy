"""List primitive ops."""

from typing import List

from mypyc.ops import (
    int_rprimitive, list_rprimitive, object_rprimitive, bool_rprimitive, ERR_MAGIC, ERR_NEVER,
    ERR_FALSE, EmitterInterface, PrimitiveOp, Value
)
from mypyc.ops_primitive import binary_op, func_op, method_op, custom_op, simple_emit


def emit_new(emitter: EmitterInterface, args: List[str], dest: str) -> None:
    # TODO: This would be better split into multiple smaller ops.
    emitter.emit_line('%s = PyList_New(%d); ' % (dest, len(args)))
    for arg in args:
        emitter.emit_line('Py_INCREF(%s);' % arg)
    emitter.emit_line('if (%s != NULL) {' % dest)
    for i, arg in enumerate(args):
        emitter.emit_line('PyList_SET_ITEM(%s, %s, %s);' % (dest, i, arg))
    emitter.emit_line('}')


new_list_op = custom_op(arg_types=[object_rprimitive],
                        result_type=list_rprimitive,
                        is_var_arg=True,
                        error_kind=ERR_MAGIC,
                        format_str = '{dest} = [{comma_args}]',
                        emit=emit_new)


list_get_item_op = method_op(
    name='__getitem__',
    arg_types=[list_rprimitive, int_rprimitive],
    result_type=object_rprimitive,
    error_kind=ERR_MAGIC,
    emit=simple_emit('{dest} = CPyList_GetItem({args[0]}, {args[1]});'))


list_set_item_op = method_op(
    name='__setitem__',
    arg_types=[list_rprimitive, int_rprimitive, object_rprimitive],
    result_type=bool_rprimitive,
    error_kind=ERR_FALSE,
    emit=simple_emit('{dest} = CPyList_SetItem({args[0]}, {args[1]}, {args[2]}) != 0;'))


list_append_op = method_op(
    name='append',
    arg_types=[list_rprimitive, object_rprimitive],
    result_type=bool_rprimitive,
    error_kind=ERR_FALSE,
    emit=simple_emit('{dest} = PyList_Append({args[0]}, {args[1]}) != -1;'))

list_extend_op = method_op(
    name='extend',
    arg_types=[list_rprimitive, object_rprimitive],
    result_type=object_rprimitive,
    error_kind=ERR_MAGIC,
    emit=simple_emit('{dest} = _PyList_Extend((PyListObject *) {args[0]}, {args[1]});'))


def emit_multiply_helper(emitter: EmitterInterface, dest: str, lst: str, num: str) -> None:
    temp = emitter.temp_name()
    emitter.emit_declaration('long long %s;' % temp)
    emitter.emit_lines(
        "%s = CPyTagged_AsLongLong(%s);" % (temp, num),
        "if (%s == -1 && PyErr_Occurred())" % temp,
        "    CPyError_OutOfMemory();",
        "%s = PySequence_Repeat(%s, %s);" % (dest, lst, temp))


def emit_multiply(emitter: EmitterInterface, args: List[str], dest: str) -> None:
    emit_multiply_helper(emitter, dest, args[0], args[1])


def emit_multiply_reversed(emitter: EmitterInterface, args: List[str], dest: str) -> None:
    emit_multiply_helper(emitter, dest, args[1], args[0])


binary_op(op='*',
          arg_types=[list_rprimitive, int_rprimitive],
          result_type=list_rprimitive,
          error_kind=ERR_MAGIC,
          format_str='{dest} = {args[0]} * {args[1]} :: list',
          emit=emit_multiply)

binary_op(op='*',
          arg_types=[int_rprimitive, list_rprimitive],
          result_type=list_rprimitive,
          error_kind=ERR_MAGIC,
          format_str='{dest} = {args[0]} * {args[1]} :: list',
          emit=emit_multiply_reversed)


def emit_len(emitter: EmitterInterface, args: List[str], dest: str) -> None:
    temp = emitter.temp_name()
    emitter.emit_declaration('long long %s;' % temp)
    emitter.emit_line('%s = PyList_GET_SIZE(%s);' % (temp, args[0]))
    emitter.emit_line('%s = CPyTagged_ShortFromLongLong(%s);' % (dest, temp))


list_len_op = func_op(name='builtins.len',
                      arg_types=[list_rprimitive],
                      result_type=int_rprimitive,
                      error_kind=ERR_NEVER,
                      emit=emit_len)
