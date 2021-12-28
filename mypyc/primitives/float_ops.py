"""Primitive float ops."""

from __future__ import annotations

from mypyc.ir.ops import ERR_MAGIC, ERR_MAGIC_OVERLAPPING, ERR_NEVER
from mypyc.ir.rtypes import float_rprimitive, int_rprimitive, object_rprimitive, str_rprimitive
from mypyc.primitives.registry import function_op, load_address_op

# Get the 'builtins.float' type object.
load_address_op(name="builtins.float", type=object_rprimitive, src="PyFloat_Type")

# float(int)
int_to_float_op = function_op(
    name="builtins.float",
    arg_types=[int_rprimitive],
    return_type=float_rprimitive,
    c_function_name="CPyFloat_FromTagged",
    error_kind=ERR_MAGIC_OVERLAPPING,
)

# float(str)
function_op(
    name="builtins.float",
    arg_types=[str_rprimitive],
    return_type=object_rprimitive,
    c_function_name="PyFloat_FromString",
    error_kind=ERR_MAGIC,
)

# abs(float)
function_op(
    name="builtins.abs",
    arg_types=[float_rprimitive],
    return_type=float_rprimitive,
    c_function_name="CPyFloat_Abs",
    error_kind=ERR_NEVER,
)

# math.sin(float)
function_op(
    name="math.sin",
    arg_types=[float_rprimitive],
    return_type=float_rprimitive,
    c_function_name="sin",
    error_kind=ERR_NEVER,
)

# math.cos(float)
function_op(
    name="math.cos",
    arg_types=[float_rprimitive],
    return_type=float_rprimitive,
    c_function_name="cos",
    error_kind=ERR_NEVER,
)

# math.sqrt(float)
function_op(
    name="math.sqrt",
    arg_types=[float_rprimitive],
    return_type=float_rprimitive,
    c_function_name="CPyFloat_Sqrt",
    error_kind=ERR_NEVER,
)
