"""Exception-related primitive ops."""

from mypyc.ir.ops import ERR_NEVER, ERR_FALSE
from mypyc.ir.rtypes import bool_rprimitive, object_rprimitive, void_rtype, exc_rtuple
from mypyc.primitives.registry import (
    simple_emit, call_emit, call_void_emit, call_and_fail_emit, custom_op,
)

# If the argument is a class, raise an instance of the class. Otherwise, assume
# that the argument is an exception object, and raise it.
#
# TODO: Making this raise conditionally is kind of hokey.
raise_exception_op = custom_op(
    arg_types=[object_rprimitive],
    result_type=bool_rprimitive,
    error_kind=ERR_FALSE,
    format_str='raise_exception({args[0]}); {dest} = 0',
    emit=call_and_fail_emit('CPy_Raise'))

# Raise StopIteration exception with the specified value (which can be NULL).
set_stop_iteration_value = custom_op(
    arg_types=[object_rprimitive],
    result_type=bool_rprimitive,
    error_kind=ERR_FALSE,
    format_str='set_stop_iteration_value({args[0]}); {dest} = 0',
    emit=call_and_fail_emit('CPyGen_SetStopIterationValue'))

# Raise exception with traceback.
# Arguments are (exception type, exception value, traceback).
raise_exception_with_tb_op = custom_op(
    arg_types=[object_rprimitive, object_rprimitive, object_rprimitive],
    result_type=bool_rprimitive,
    error_kind=ERR_FALSE,
    format_str='raise_exception_with_tb({args[0]}, {args[1]}, {args[2]}); {dest} = 0',
    emit=call_and_fail_emit('CPyErr_SetObjectAndTraceback'))

# Reraise the currently raised exception.
reraise_exception_op = custom_op(
    arg_types=[],
    result_type=bool_rprimitive,
    error_kind=ERR_FALSE,
    format_str='reraise_exc; {dest} = 0',
    emit=call_and_fail_emit('CPy_Reraise'))

# Propagate exception if the CPython error indicator is set (an exception was raised).
no_err_occurred_op = custom_op(
    arg_types=[],
    result_type=bool_rprimitive,
    error_kind=ERR_FALSE,
    format_str='{dest} = no_err_occurred',
    emit=call_emit('CPy_NoErrOccured'))

# Assert that the error indicator has been set.
assert_err_occured_op = custom_op(
    arg_types=[],
    result_type=void_rtype,
    error_kind=ERR_NEVER,
    format_str='assert_err_occurred',
    emit=simple_emit('assert(PyErr_Occurred() != NULL && "failure w/o err!");'))

# Keep propagating a raised exception by unconditionally giving an error value.
# This doesn't actually raise an exception.
keep_propagating_op = custom_op(
    arg_types=[],
    result_type=bool_rprimitive,
    error_kind=ERR_FALSE,
    format_str='{dest} = keep_propagating',
    emit=simple_emit('{dest} = 0;'))

# Catches a propagating exception and makes it the "currently
# handled exception" (by sticking it into sys.exc_info()). Returns the
# exception that was previously being handled, which must be restored
# later.
error_catch_op = custom_op(
    arg_types=[],
    result_type=exc_rtuple,
    error_kind=ERR_NEVER,
    format_str='{dest} = error_catch',
    emit=call_emit('CPy_CatchError'))

# Restore an old "currently handled exception" returned from.
# error_catch (by sticking it into sys.exc_info())
restore_exc_info_op = custom_op(
    arg_types=[exc_rtuple],
    result_type=void_rtype,
    error_kind=ERR_NEVER,
    format_str='restore_exc_info {args[0]}',
    emit=call_void_emit('CPy_RestoreExcInfo'))

# Checks whether the exception currently being handled matches a particular type.
exc_matches_op = custom_op(
    arg_types=[object_rprimitive],
    result_type=bool_rprimitive,
    error_kind=ERR_NEVER,
    format_str='{dest} = exc_matches {args[0]}',
    emit=call_emit('CPy_ExceptionMatches'))

# Get the value of the exception currently being handled.
get_exc_value_op = custom_op(
    arg_types=[],
    result_type=object_rprimitive,
    error_kind=ERR_NEVER,
    format_str='{dest} = get_exc_value',
    emit=call_emit('CPy_GetExcValue'))

# Get exception info (exception type, exception instance, traceback object).
get_exc_info_op = custom_op(
    arg_types=[],
    result_type=exc_rtuple,
    error_kind=ERR_NEVER,
    format_str='{dest} = get_exc_info',
    emit=call_emit('CPy_GetExcInfo'))
