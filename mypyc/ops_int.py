from typing import List

from mypyc.ops import (
    PrimitiveOp, int_rprimitive, RType, EmitterInterface, OpDescription, ERR_NEVER,
)
from mypyc.ops_primitive import binary_op, unary_op, simple_emit


def int_binary_op(op: str, c_func_name: str) -> None:
    binary_op(op=op,
              arg_types=[int_rprimitive, int_rprimitive],
              result_type=int_rprimitive,
              error_kind=ERR_NEVER,
              format_str='{dest} = {args[0]} %s {args[1]} :: int' % op,
              emit=simple_emit('{dest} = %s({args[0]}, {args[1]});' % c_func_name))


int_binary_op('+', 'CPyTagged_Add')
int_binary_op('-', 'CPyTagged_Subtract')
int_binary_op('*', 'CPyTagged_Multiply')
int_binary_op('//', 'CPyTagged_FloorDivide')
int_binary_op('%', 'CPyTagged_Remainder')


def int_unary_op(op: str, c_func_name: str) -> OpDescription:
    return unary_op(op=op,
                    arg_type=int_rprimitive,
                    result_type=int_rprimitive,
                    error_kind=ERR_NEVER,
                    format_str='{dest} = %s{args[0]} :: int' % op,
                    emit=simple_emit('{dest} = %s({args[0]});' % c_func_name))


int_neg_op = int_unary_op('-', 'CPyTagged_Negate')
