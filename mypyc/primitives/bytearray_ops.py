"""Primitive bytearray ops."""

from __future__ import annotations

from mypyc.ir.ops import ERR_MAGIC, ERR_NEVER
from mypyc.ir.rtypes import bit_rprimitive, bytearray_rprimitive, object_rprimitive
from mypyc.primitives.registry import function_op, load_address_op

# Get the 'bytearray' type object.
load_address_op(name="builtins.bytearray", type=object_rprimitive, src="PyByteArray_Type")

# bytearray(obj)
function_op(
    name="builtins.bytearray",
    arg_types=[object_rprimitive],
    return_type=bytearray_rprimitive,
    c_function_name="PyByteArray_FromObject",
    error_kind=ERR_MAGIC,
)

# translate isinstance(obj, bytearray)
isinstance_bytearray = function_op(
    name="builtins.isinstance",
    arg_types=[object_rprimitive],
    return_type=bit_rprimitive,
    c_function_name="PyByteArray_Check",
    error_kind=ERR_NEVER,
)
