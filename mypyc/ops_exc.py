"""Exception-related primitive ops."""

from typing import List

from mypyc.ops import (
    EmitterInterface, PrimitiveOp, none_rprimitive, bool_rprimitive, object_rprimitive,
    exc_rtuple,
    ERR_NEVER, ERR_MAGIC, ERR_FALSE
)
from mypyc.ops_primitive import (
    simple_emit, func_op, method_op, custom_op,
    negative_int_emit,
)


# TODO: Making this raise conditionally is kind of hokey.
raise_exception_op = custom_op(
    arg_types=[object_rprimitive, object_rprimitive],
    result_type=bool_rprimitive,
    error_kind=ERR_FALSE,
    format_str = 'raise_exception({args[0]}, {args[1]}); {dest} = 0',
    emit=simple_emit('PyErr_SetObject({args[0]}, {args[1]}); {dest} = 0;'))

# This having a return value is pretty ugly
clear_exception_op = custom_op(
    arg_types=[],
    result_type=bool_rprimitive,
    error_kind=ERR_NEVER,
    format_str = 'clear_exception(); {dest} = 0',
    emit=simple_emit('PyErr_Clear(); {dest} = 0; (void){dest};'))

no_err_occurred_op = func_op(name='no_err_occurred',
                             arg_types=[],
                             result_type=bool_rprimitive,
                             error_kind=ERR_FALSE,
                             emit=simple_emit('{dest} = (PyErr_Occurred() == NULL);'))
