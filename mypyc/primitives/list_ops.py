"""List primitive ops."""

from typing import List

from mypyc.ir.ops import ERR_MAGIC, ERR_NEVER, ERR_FALSE, ERR_NEG_INT, EmitterInterface
from mypyc.ir.rtypes import (
    int_rprimitive, short_int_rprimitive, list_rprimitive, object_rprimitive, bool_rprimitive,
    c_int_rprimitive
)
from mypyc.primitives.registry import (
    custom_op, load_address_op, call_emit, c_function_op, c_binary_op, c_method_op
)


# Get the 'builtins.list' type object.
load_address_op(
    name='builtins.list',
    type=object_rprimitive,
    src='PyList_Type')

# list(obj)
to_list = c_function_op(
    name='builtins.list',
    arg_types=[object_rprimitive],
    return_type=list_rprimitive,
    c_function_name='PySequence_List',
    error_kind=ERR_MAGIC,
)


def emit_new(emitter: EmitterInterface, args: List[str], dest: str) -> None:
    # TODO: This would be better split into multiple smaller ops.
    emitter.emit_line('%s = PyList_New(%d); ' % (dest, len(args)))
    emitter.emit_line('if (likely(%s != NULL)) {' % dest)
    for i, arg in enumerate(args):
        emitter.emit_line('PyList_SET_ITEM(%s, %s, %s);' % (dest, i, arg))
    emitter.emit_line('}')


# Construct a list from values: [item1, item2, ....]
new_list_op = custom_op(arg_types=[object_rprimitive],
                        result_type=list_rprimitive,
                        is_var_arg=True,
                        error_kind=ERR_MAGIC,
                        steals=True,
                        format_str='{dest} = [{comma_args}]',
                        emit=emit_new)


# list[index] (for an integer index)
list_get_item_op = c_method_op(
    name='__getitem__',
    arg_types=[list_rprimitive, int_rprimitive],
    return_type=object_rprimitive,
    c_function_name='CPyList_GetItem',
    error_kind=ERR_MAGIC)

# Version with no int bounds check for when it is known to be short
c_method_op(
    name='__getitem__',
    arg_types=[list_rprimitive, short_int_rprimitive],
    return_type=object_rprimitive,
    c_function_name='CPyList_GetItemShort',
    error_kind=ERR_MAGIC,
    priority=2)

# This is unsafe because it assumes that the index is a non-negative short integer
# that is in-bounds for the list.
list_get_item_unsafe_op = custom_op(
    name='__getitem__',
    arg_types=[list_rprimitive, short_int_rprimitive],
    result_type=object_rprimitive,
    error_kind=ERR_NEVER,
    format_str='{dest} = {args[0]}[{args[1]}] :: unsafe list',
    emit=call_emit('CPyList_GetItemUnsafe'))

# list[index] = obj
list_set_item_op = c_method_op(
    name='__setitem__',
    arg_types=[list_rprimitive, int_rprimitive, object_rprimitive],
    return_type=bool_rprimitive,
    c_function_name='CPyList_SetItem',
    error_kind=ERR_FALSE,
    steals=[False, False, True])

# list.append(obj)
list_append_op = c_method_op(
    name='append',
    arg_types=[list_rprimitive, object_rprimitive],
    return_type=c_int_rprimitive,
    c_function_name='PyList_Append',
    error_kind=ERR_NEG_INT)

# list.extend(obj)
list_extend_op = c_method_op(
    name='extend',
    arg_types=[list_rprimitive, object_rprimitive],
    return_type=object_rprimitive,
    c_function_name='CPyList_Extend',
    error_kind=ERR_MAGIC)

# list.pop()
list_pop_last = c_method_op(
    name='pop',
    arg_types=[list_rprimitive],
    return_type=object_rprimitive,
    c_function_name='CPyList_PopLast',
    error_kind=ERR_MAGIC)

# list.pop(index)
list_pop = c_method_op(
    name='pop',
    arg_types=[list_rprimitive, int_rprimitive],
    return_type=object_rprimitive,
    c_function_name='CPyList_Pop',
    error_kind=ERR_MAGIC)

# list.count(obj)
c_method_op(
    name='count',
    arg_types=[list_rprimitive, object_rprimitive],
    return_type=short_int_rprimitive,
    c_function_name='CPyList_Count',
    error_kind=ERR_MAGIC)

# list * int
c_binary_op(
    name='*',
    arg_types=[list_rprimitive, int_rprimitive],
    return_type=list_rprimitive,
    c_function_name='CPySequence_Multiply',
    error_kind=ERR_MAGIC)

# int * list
c_binary_op(name='*',
            arg_types=[int_rprimitive, list_rprimitive],
            return_type=list_rprimitive,
            c_function_name='CPySequence_RMultiply',
            error_kind=ERR_MAGIC)


def emit_len(emitter: EmitterInterface, args: List[str], dest: str) -> None:
    temp = emitter.temp_name()
    emitter.emit_declaration('Py_ssize_t %s;' % temp)
    emitter.emit_line('%s = PyList_GET_SIZE(%s);' % (temp, args[0]))
    emitter.emit_line('%s = CPyTagged_ShortFromSsize_t(%s);' % (dest, temp))
