from mypyc.ir.ops import OpDescription, ERR_NEVER, ERR_MAGIC
from mypyc.ir.rtypes import (
    int_rprimitive, bool_rprimitive, float_rprimitive, object_rprimitive, short_int_rprimitive,
    str_rprimitive, RType
)
from mypyc.primitives.registry import (
    name_ref_op, binary_op, unary_op, func_op, custom_op,
    simple_emit,
    call_emit,
)

# These int constructors produce object_rprimitives that then need to be unboxed
# I guess unboxing ourselves would save a check and branch though?

# For ordinary calls to int() we use a name_ref to the type
name_ref_op('builtins.int',
            result_type=object_rprimitive,
            error_kind=ERR_NEVER,
            emit=simple_emit('{dest} = (PyObject *)&PyLong_Type;'),
            is_borrowed=True)

# Convert from a float. We could do a bit better directly.
func_op(
    name='builtins.int',
    arg_types=[float_rprimitive],
    result_type=object_rprimitive,
    error_kind=ERR_MAGIC,
    emit=call_emit('CPyLong_FromFloat'),
    priority=1)

func_op(
    name='builtins.int',
    arg_types=[str_rprimitive],
    result_type=object_rprimitive,
    error_kind=ERR_MAGIC,
    emit=call_emit('CPyLong_FromStr'),
    priority=1)

func_op(
    name='builtins.int',
    arg_types=[str_rprimitive, int_rprimitive],
    result_type=object_rprimitive,
    error_kind=ERR_MAGIC,
    emit=call_emit('CPyLong_FromStrWithBase'),
    priority=1)


def int_binary_op(op: str, c_func_name: str,
                  result_type: RType = int_rprimitive,
                  error_kind: int = ERR_NEVER) -> None:
    binary_op(op=op,
              arg_types=[int_rprimitive, int_rprimitive],
              result_type=result_type,
              error_kind=error_kind,
              format_str='{dest} = {args[0]} %s {args[1]} :: int' % op,
              emit=call_emit(c_func_name))


def int_compare_op(op: str, c_func_name: str) -> None:
    int_binary_op(op, c_func_name, bool_rprimitive)
    # Generate a straight compare if we know both sides are short
    binary_op(op=op,
              arg_types=[short_int_rprimitive, short_int_rprimitive],
              result_type=bool_rprimitive,
              error_kind=ERR_NEVER,
              format_str='{dest} = {args[0]} %s {args[1]} :: short_int' % op,
              emit=simple_emit(
                  '{dest} = (Py_ssize_t){args[0]} %s (Py_ssize_t){args[1]};' % op),
              priority=2)


int_binary_op('+', 'CPyTagged_Add')
int_binary_op('-', 'CPyTagged_Subtract')
int_binary_op('*', 'CPyTagged_Multiply')
# Divide and remainder we honestly propagate errors from because they
# can raise ZeroDivisionError
int_binary_op('//', 'CPyTagged_FloorDivide', error_kind=ERR_MAGIC)
int_binary_op('%', 'CPyTagged_Remainder', error_kind=ERR_MAGIC)

# this should work because assignment operators are parsed differently
# and the code in irbuild that handles it does the assignment
# regardless of whether or not the operator works in place anyway
int_binary_op('+=', 'CPyTagged_Add')
int_binary_op('-=', 'CPyTagged_Subtract')
int_binary_op('*=', 'CPyTagged_Multiply')
int_binary_op('//=', 'CPyTagged_FloorDivide', error_kind=ERR_MAGIC)
int_binary_op('%=', 'CPyTagged_Remainder', error_kind=ERR_MAGIC)

int_compare_op('==', 'CPyTagged_IsEq')
int_compare_op('!=', 'CPyTagged_IsNe')
int_compare_op('<', 'CPyTagged_IsLt')
int_compare_op('<=', 'CPyTagged_IsLe')
int_compare_op('>', 'CPyTagged_IsGt')
int_compare_op('>=', 'CPyTagged_IsGe')

unsafe_short_add = custom_op(
    arg_types=[int_rprimitive, int_rprimitive],
    result_type=short_int_rprimitive,
    error_kind=ERR_NEVER,
    format_str='{dest} = {args[0]} + {args[1]} :: short_int',
    emit=simple_emit('{dest} = {args[0]} + {args[1]};'))


def int_unary_op(op: str, c_func_name: str) -> OpDescription:
    return unary_op(op=op,
                    arg_type=int_rprimitive,
                    result_type=int_rprimitive,
                    error_kind=ERR_NEVER,
                    format_str='{dest} = %s{args[0]} :: int' % op,
                    emit=call_emit(c_func_name))


int_neg_op = int_unary_op('-', 'CPyTagged_Negate')
