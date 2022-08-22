"""Primitive float ops."""

from __future__ import annotations

from mypyc.ir.ops import ERR_MAGIC
from mypyc.ir.rtypes import float_rprimitive, object_rprimitive, str_rprimitive
from mypyc.primitives.registry import function_op, load_address_op

# Get the 'builtins.float' type object.
load_address_op(name="builtins.float", type=object_rprimitive, src="PyFloat_Type")

# float(str)
function_op(
    name="builtins.float",
    arg_types=[str_rprimitive],
    return_type=float_rprimitive,
    c_function_name="PyFloat_FromString",
    error_kind=ERR_MAGIC,
)

# abs(float)
function_op(
    name="builtins.abs",
    arg_types=[float_rprimitive],
    return_type=float_rprimitive,
    c_function_name="PyNumber_Absolute",
    error_kind=ERR_MAGIC,
)
