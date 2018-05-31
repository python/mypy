"""Primitive dict ops."""

from typing import List

from mypyc.ops import (
    EmitterInterface, PrimitiveOp, dict_rprimitive, object_rprimitive, bool_rprimitive, ERR_FALSE,
    ERR_MAGIC
)
from mypyc.ops_primitive import method_op, binary_op, func_op, simple_emit


def emit_get_item(emitter: EmitterInterface, args: List[str], dest: str) -> None:
    emitter.emit_lines('%s = PyDict_GetItemWithError(%s, %s);' % (dest, args[0], args[1]),
                       'if (!%s)' % dest,
                       '    PyErr_SetObject(PyExc_KeyError, %s);' % args[1],
                       'else',
                       '    Py_INCREF(%s);' % dest)


dict_get_item_op = method_op(
    name='builtins.dict.__getitem__',
    arg_types=[dict_rprimitive, object_rprimitive],
    result_type=object_rprimitive,
    error_kind=ERR_MAGIC,
    emit=emit_get_item)


dict_set_item_op = method_op(
    name='builtins.dict.__setitem__',
    arg_types=[dict_rprimitive, object_rprimitive, object_rprimitive],
    result_type=bool_rprimitive,
    error_kind=ERR_FALSE,
    emit=simple_emit('{dest} = PyDict_SetItem({args[0]}, {args[1]}, {args[2]}) >= 0;'))


def emit_in(emitter: EmitterInterface, args: List[str], dest: str) -> None:
    temp = emitter.temp_name()
    emitter.emit_lines('int %s = PyDict_Contains(%s, %s);' % (temp, args[1], args[0]),
                       'if (%s < 0)' % temp,
                       '    %s = %s;' % (dest, bool_rprimitive.c_error_value()),
                       'else',
                       '    %s = %s;' % (dest, temp))


binary_op(op='in',
          arg_types=[object_rprimitive, dict_rprimitive],
          result_type=bool_rprimitive,
          error_kind=ERR_MAGIC,
          format_str='{dest} = {args[0]} in {args[1]} :: dict',
          emit=emit_in)


# NOTE: PyDict_Update is technically not equivalent to update, but the cases where it
# differs (when the second argument has no keys) should never typecheck for us, so the
# difference is irrelevant.
dict_update_op = method_op(
    name='builtins.dict.update',
    arg_types=[dict_rprimitive, object_rprimitive],
    result_type=None,
    error_kind=ERR_FALSE,
    emit=simple_emit('{dest} = PyDict_Update({args[0]}, {args[1]}) != -1;'))


new_dict_op = func_op(
    name='builtins.dict',
    arg_types=[],
    result_type=dict_rprimitive,
    error_kind=ERR_MAGIC,
    format_str='{dest} = {{}}',
    emit=simple_emit('{dest} = PyDict_New();'))
