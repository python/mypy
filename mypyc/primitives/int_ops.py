"""Integer primitive ops.

These mostly operate on (usually) unboxed integers that use a tagged pointer
representation (CPyTagged).

See also the documentation for mypyc.rtypes.int_rprimitive.
"""

from typing import Dict, NamedTuple
from mypyc.ir.ops import ERR_NEVER, ERR_MAGIC, BinaryIntOp
from mypyc.ir.rtypes import (
    int_rprimitive, bool_rprimitive, float_rprimitive, object_rprimitive, short_int_rprimitive,
    str_rprimitive, RType
)
from mypyc.primitives.registry import (
    name_ref_op, binary_op, custom_op, simple_emit, name_emit,
    c_unary_op, CFunctionDescription, c_function_op, c_binary_op, c_custom_op
)

# These int constructors produce object_rprimitives that then need to be unboxed
# I guess unboxing ourselves would save a check and branch though?

# Get the type object for 'builtins.int'.
# For ordinary calls to int() we use a name_ref to the type
name_ref_op('builtins.int',
            result_type=object_rprimitive,
            error_kind=ERR_NEVER,
            emit=name_emit('&PyLong_Type', target_type='PyObject *'),
            is_borrowed=True)

# Convert from a float to int. We could do a bit better directly.
c_function_op(
    name='builtins.int',
    arg_types=[float_rprimitive],
    return_type=object_rprimitive,
    c_function_name='CPyLong_FromFloat',
    error_kind=ERR_MAGIC)

# int(string)
c_function_op(
    name='builtins.int',
    arg_types=[str_rprimitive],
    return_type=object_rprimitive,
    c_function_name='CPyLong_FromStr',
    error_kind=ERR_MAGIC)

# int(string, base)
c_function_op(
    name='builtins.int',
    arg_types=[str_rprimitive, int_rprimitive],
    return_type=object_rprimitive,
    c_function_name='CPyLong_FromStrWithBase',
    error_kind=ERR_MAGIC)

# str(n) on ints
c_function_op(
    name='builtins.str',
    arg_types=[int_rprimitive],
    return_type=str_rprimitive,
    c_function_name='CPyTagged_Str',
    error_kind=ERR_MAGIC,
    priority=2)

# We need a specialization for str on bools also since the int one is wrong...
c_function_op(
    name='builtins.str',
    arg_types=[bool_rprimitive],
    return_type=str_rprimitive,
    c_function_name='CPyBool_Str',
    error_kind=ERR_MAGIC,
    priority=3)


def int_binary_op(name: str, c_function_name: str,
                  return_type: RType = int_rprimitive,
                  error_kind: int = ERR_NEVER) -> None:
    c_binary_op(name=name,
                arg_types=[int_rprimitive, int_rprimitive],
                return_type=return_type,
                c_function_name=c_function_name,
                error_kind=error_kind)


def int_compare_op(name: str, c_function_name: str) -> None:
    int_binary_op(name, c_function_name, bool_rprimitive)
    # Generate a straight compare if we know both sides are short
    op = name
    binary_op(op=op,
              arg_types=[short_int_rprimitive, short_int_rprimitive],
              result_type=bool_rprimitive,
              error_kind=ERR_NEVER,
              format_str='{dest} = {args[0]} %s {args[1]} :: short_int' % op,
              emit=simple_emit(
                  '{dest} = (Py_ssize_t){args[0]} %s (Py_ssize_t){args[1]};' % op),
              priority=2)


# Binary, unary and augmented assignment operations that operate on CPyTagged ints.

int_binary_op('+', 'CPyTagged_Add')
int_binary_op('-', 'CPyTagged_Subtract')
int_binary_op('*', 'CPyTagged_Multiply')
# Divide and remainder we honestly propagate errors from because they
# can raise ZeroDivisionError
int_binary_op('//', 'CPyTagged_FloorDivide', error_kind=ERR_MAGIC)
int_binary_op('%', 'CPyTagged_Remainder', error_kind=ERR_MAGIC)

# This should work because assignment operators are parsed differently
# and the code in irbuild that handles it does the assignment
# regardless of whether or not the operator works in place anyway.
int_binary_op('+=', 'CPyTagged_Add')
int_binary_op('-=', 'CPyTagged_Subtract')
int_binary_op('*=', 'CPyTagged_Multiply')
int_binary_op('//=', 'CPyTagged_FloorDivide', error_kind=ERR_MAGIC)
int_binary_op('%=', 'CPyTagged_Remainder', error_kind=ERR_MAGIC)

# Add short integers and assume that it doesn't overflow or underflow.
# Assume that the operands are not big integers.
unsafe_short_add = custom_op(
    arg_types=[int_rprimitive, int_rprimitive],
    result_type=short_int_rprimitive,
    error_kind=ERR_NEVER,
    format_str='{dest} = {args[0]} + {args[1]} :: short_int',
    emit=simple_emit('{dest} = {args[0]} + {args[1]};'))


def int_unary_op(name: str, c_function_name: str) -> CFunctionDescription:
    return c_unary_op(name=name,
                      arg_type=int_rprimitive,
                      return_type=int_rprimitive,
                      c_function_name=c_function_name,
                      error_kind=ERR_NEVER)


int_neg_op = int_unary_op('-', 'CPyTagged_Negate')

# integer comparsion operation implementation related:

# Description for building int logical ops
# For each field:
# binary_op_variant: identify which BinaryIntOp to use when operands are short integers
# c_func_description: the C function to call when operands are tagged integers
# c_func_negated: whether to negate the C function call's result
# c_func_swap_operands: whether to swap lhs and rhs when call the function
IntLogicalOpDescrption = NamedTuple(
    'IntLogicalOpDescrption',  [('binary_op_variant', int),
                                ('c_func_description', CFunctionDescription),
                                ('c_func_negated', bool),
                                ('c_func_swap_operands', bool)])

# description for equal operation on two boxed tagged integers
int_equal_ = c_custom_op(
    arg_types=[int_rprimitive, int_rprimitive],
    return_type=bool_rprimitive,
    c_function_name='CPyTagged_IsEq_',
    error_kind=ERR_NEVER)

int_less_than_ = c_custom_op(
    arg_types=[int_rprimitive, int_rprimitive],
    return_type=bool_rprimitive,
    c_function_name='CPyTagged_IsLt_',
    error_kind=ERR_NEVER)

# provide mapping from textual op to short int's op variant and boxed int's description
# note these are not complete implementations
int_logical_op_mapping = {
    '==': IntLogicalOpDescrption(BinaryIntOp.EQ, int_equal_, False, False),
    '!=': IntLogicalOpDescrption(BinaryIntOp.NEQ, int_equal_, True, False),
    '<': IntLogicalOpDescrption(BinaryIntOp.SLT, int_less_than_, False, False),
    '<=': IntLogicalOpDescrption(BinaryIntOp.SLE, int_less_than_, True, True),
    '>': IntLogicalOpDescrption(BinaryIntOp.SGT, int_less_than_, False, True),
    '>=': IntLogicalOpDescrption(BinaryIntOp.SGE, int_less_than_, True, False),
}  # type: Dict[str, IntLogicalOpDescrption]
