"""Primitive str ops."""

from typing import List, Callable

from mypyc.ir.ops import ERR_MAGIC, EmitterInterface, EmitCallback
from mypyc.ir.rtypes import (
    RType, object_rprimitive, str_rprimitive, bool_rprimitive, int_rprimitive, list_rprimitive
)
from mypyc.primitives.registry import (
    binary_op, simple_emit, method_op, call_emit, c_method_op, c_binary_op, c_function_op,
    load_address_op
)


# Get the 'str' type object.
load_address_op(
    name='builtins.str',
    type=object_rprimitive,
    src='PyUnicode_Type')

# str(obj)
c_function_op(
    name='builtins.str',
    arg_types=[object_rprimitive],
    return_type=str_rprimitive,
    c_function_name='PyObject_Str',
    error_kind=ERR_MAGIC)

# str1 + str2
c_binary_op(name='+',
            arg_types=[str_rprimitive, str_rprimitive],
            return_type=str_rprimitive,
            c_function_name='PyUnicode_Concat',
            error_kind=ERR_MAGIC)

# str.join(obj)
c_method_op(
    name='join',
    arg_types=[str_rprimitive, object_rprimitive],
    return_type=str_rprimitive,
    c_function_name='PyUnicode_Join',
    error_kind=ERR_MAGIC
)

# str[index] (for an int index)
c_method_op(
    name='__getitem__',
    arg_types=[str_rprimitive, int_rprimitive],
    return_type=str_rprimitive,
    c_function_name='CPyStr_GetItem',
    error_kind=ERR_MAGIC
)

# str.split(...)
str_split_types = [str_rprimitive, str_rprimitive, int_rprimitive]  # type: List[RType]
str_split_emits = [simple_emit('{dest} = PyUnicode_Split({args[0]}, NULL, -1);'),
                   simple_emit('{dest} = PyUnicode_Split({args[0]}, {args[1]}, -1);'),
                   call_emit('CPyStr_Split')] \
                   # type: List[EmitCallback]
for i in range(len(str_split_types)):
    method_op(
        name='split',
        arg_types=str_split_types[0:i+1],
        result_type=list_rprimitive,
        error_kind=ERR_MAGIC,
        emit=str_split_emits[i])

# str1 += str2
#
# PyUnicodeAppend makes an effort to reuse the LHS when the refcount
# is 1. This is super dodgy but oh well, the interpreter does it.
c_binary_op(name='+=',
            arg_types=[str_rprimitive, str_rprimitive],
            return_type=str_rprimitive,
            c_function_name='CPyStr_Append',
            error_kind=ERR_MAGIC,
            steals=[True, False])


def emit_str_compare(comparison: str) -> Callable[[EmitterInterface, List[str], str], None]:
    def emit(emitter: EmitterInterface, args: List[str], dest: str) -> None:
        temp = emitter.temp_name()
        emitter.emit_declaration('int %s;' % temp)
        emitter.emit_lines(
            '%s = PyUnicode_Compare(%s, %s);' % (temp, args[0], args[1]),
            'if (%s == -1 && PyErr_Occurred())' % temp,
            '    %s = 2;' % dest,
            'else',
            '    %s = (%s %s);' % (dest, temp, comparison))

    return emit


# str1 == str2
binary_op(op='==',
          arg_types=[str_rprimitive, str_rprimitive],
          result_type=bool_rprimitive,
          error_kind=ERR_MAGIC,
          emit=emit_str_compare('== 0'))

# str1 != str2
binary_op(op='!=',
          arg_types=[str_rprimitive, str_rprimitive],
          result_type=bool_rprimitive,
          error_kind=ERR_MAGIC,
          emit=emit_str_compare('!= 0'))
