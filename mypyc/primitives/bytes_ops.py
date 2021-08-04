"""Primitive bytes ops."""

from mypyc.ir.ops import ERR_MAGIC
from mypyc.ir.rtypes import (
    object_rprimitive, bytes_rprimitive, list_rprimitive, dict_rprimitive,
    str_rprimitive, RUnion
)
from mypyc.primitives.registry import load_address_op, function_op


# Get the 'bytes' type object.
load_address_op(
    name='builtins.bytes',
    type=object_rprimitive,
    src='PyBytes_Type')

# bytes(obj)
function_op(
    name='builtins.bytes',
    arg_types=[RUnion([list_rprimitive, dict_rprimitive, str_rprimitive])],
    return_type=bytes_rprimitive,
    c_function_name='PyBytes_FromObject',
    error_kind=ERR_MAGIC)

# bytearray(obj)
function_op(
    name='builtins.bytearray',
    arg_types=[object_rprimitive],
    return_type=bytes_rprimitive,
    c_function_name='PyByteArray_FromObject',
    error_kind=ERR_MAGIC)
