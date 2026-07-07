from mypyc.ir.deps import LIBRT_THREADING
from mypyc.ir.ops import ERR_MAGIC, ERR_NEVER
from mypyc.ir.rtypes import bool_rprimitive, lock_rprimitive, none_rprimitive
from mypyc.primitives.registry import function_op, method_op

# Lock()
function_op(
    name="librt.threading.Lock",
    arg_types=[],
    return_type=lock_rprimitive,
    c_function_name="LibRTThreading_Lock_new_internal",
    error_kind=ERR_MAGIC,
    dependencies=[LIBRT_THREADING],
)

# Lock.acquire() -- blocking acquire, returns True unless it raises
lock_acquire_op = method_op(
    name="acquire",
    arg_types=[lock_rprimitive],
    return_type=bool_rprimitive,
    c_function_name="LibRTThreading_Lock_acquire_internal",
    error_kind=ERR_MAGIC,
    dependencies=[LIBRT_THREADING],
)

# Lock.acquire(blocking) -- acquire with explicit blocking argument
method_op(
    name="acquire",
    arg_types=[lock_rprimitive, bool_rprimitive],
    return_type=bool_rprimitive,
    c_function_name="LibRTThreading_Lock_acquire_blocking_internal",
    error_kind=ERR_MAGIC,
    dependencies=[LIBRT_THREADING],
)

# Lock.release()
lock_release_op = method_op(
    name="release",
    arg_types=[lock_rprimitive],
    return_type=none_rprimitive,
    c_function_name="LibRTThreading_Lock_release_internal",
    error_kind=ERR_MAGIC,
    dependencies=[LIBRT_THREADING],
)

# Lock.locked()
method_op(
    name="locked",
    arg_types=[lock_rprimitive],
    return_type=bool_rprimitive,
    c_function_name="LibRTThreading_Lock_locked_internal",
    error_kind=ERR_NEVER,
    dependencies=[LIBRT_THREADING],
)
