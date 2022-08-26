"""Primitive float ops."""

from mypyc.ir.ops import ERR_MAGIC
from mypyc.ir.rtypes import (
    str_rprimitive, float_rprimitive, object_rprimitive
)
from mypyc.primitives.registry import (
    load_address_op, function_op
)

# Get the 'builtins.float' type object.
load_address_op(
    name='builtins.float',
    type=object_rprimitive,
    src='PyFloat_Type')

# float(str)
function_op(
    name='builtins.float',
    arg_types=[str_rprimitive],
    return_type=float_rprimitive,
    c_function_name='PyFloat_FromString',
    error_kind=ERR_MAGIC)

# abs(float)
function_op(
    name='builtins.abs',
    arg_types=[float_rprimitive],
    return_type=float_rprimitive,
    c_function_name='PyNumber_Absolute',
    error_kind=ERR_MAGIC)
