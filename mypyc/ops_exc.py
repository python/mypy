"""Exception-related primitive ops."""

from typing import List

from mypyc.ops import (
    EmitterInterface, PrimitiveOp, none_rprimitive, bool_rprimitive, object_rprimitive,
    void_rtype,
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

clear_exception_op = custom_op(
    arg_types=[],
    result_type=void_rtype,
    error_kind=ERR_NEVER,
    format_str = 'clear_exception',
    emit=simple_emit('PyErr_Clear();'))

no_err_occurred_op = func_op(name='no_err_occurred',
                             arg_types=[],
                             result_type=bool_rprimitive,
                             error_kind=ERR_FALSE,
                             emit=simple_emit('{dest} = (PyErr_Occurred() == NULL);'))

error_catch_op = custom_op(
    arg_types=[],
    result_type=exc_rtuple,
    error_kind=ERR_NEVER,
    format_str = '{dest} = err_catch',
    emit=simple_emit('CPy_CatchError(&{dest}.f0, &{dest}.f1, &{dest}.f2);'))

clear_exc_info_op = custom_op(
    arg_types=[],
    result_type=void_rtype,
    error_kind=ERR_NEVER,
    format_str = 'clear_exc_info',
    emit=simple_emit('PyErr_SetExcInfo(NULL, NULL, NULL);'))
