"""Primitive bytes ops."""

from mypyc.ir.ops import ERR_MAGIC
from mypyc.ir.rtypes import object_rprimitive, bytes_rprimitive, int_rprimitive
from mypyc.primitives.registry import load_address_op, function_op


# Get the 'bytes' type object.
load_address_op(
    name='builtins.bytes',
    type=object_rprimitive,
    src='PyBytes_Type')

# bytes(obj)
function_op(
    name='builtins.bytes',
    arg_types=[object_rprimitive],
    return_type=bytes_rprimitive,
    c_function_name='PyBytes_FromObject',
    error_kind=ERR_MAGIC)

# bytes(int)
function_op(
    name='builtins.bytes',
    arg_types=[int_rprimitive],
    return_type=bytes_rprimitive,
    c_function_name='CPyBytes_FromInt',
    error_kind=ERR_MAGIC,
    priority=2)

# bytearray(obj)
function_op(
    name='builtins.bytearray',
    arg_types=[object_rprimitive],
    return_type=bytes_rprimitive,
    c_function_name='PyByteArray_FromObject',
    error_kind=ERR_MAGIC)
