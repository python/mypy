from mypyc.ir.deps import BYTES_WRITER_EXTRA_OPS, LIBRT_STRINGS
from mypyc.ir.ops import ERR_MAGIC, ERR_NEVER
from mypyc.ir.rtypes import (
    bool_rprimitive,
    bytes_rprimitive,
    bytes_writer_rprimitive,
    int64_rprimitive,
    none_rprimitive,
    short_int_rprimitive,
    uint8_rprimitive,
    void_rtype,
)
from mypyc.primitives.registry import custom_primitive_op, function_op, method_op

function_op(
    name="librt.strings.BytesWriter",
    arg_types=[],
    return_type=bytes_writer_rprimitive,
    c_function_name="LibRTStrings_BytesWriter_internal",
    error_kind=ERR_MAGIC,
    experimental=True,
    dependencies=[LIBRT_STRINGS],
)

method_op(
    name="getvalue",
    arg_types=[bytes_writer_rprimitive],
    return_type=bytes_rprimitive,
    c_function_name="LibRTStrings_BytesWriter_getvalue_internal",
    error_kind=ERR_MAGIC,
    experimental=True,
    dependencies=[LIBRT_STRINGS],
)

method_op(
    name="write",
    arg_types=[bytes_writer_rprimitive, bytes_rprimitive],
    return_type=none_rprimitive,
    c_function_name="CPyBytesWriter_Write",
    error_kind=ERR_MAGIC,
    experimental=True,
    dependencies=[LIBRT_STRINGS, BYTES_WRITER_EXTRA_OPS],
)

method_op(
    name="append",
    arg_types=[bytes_writer_rprimitive, uint8_rprimitive],
    return_type=none_rprimitive,
    c_function_name="CPyBytesWriter_Append",
    error_kind=ERR_MAGIC,
    experimental=True,
    dependencies=[LIBRT_STRINGS, BYTES_WRITER_EXTRA_OPS],
)

method_op(
    name="truncate",
    arg_types=[bytes_writer_rprimitive, int64_rprimitive],
    return_type=none_rprimitive,
    c_function_name="LibRTStrings_BytesWriter_truncate_internal",
    error_kind=ERR_MAGIC,
    experimental=True,
    dependencies=[LIBRT_STRINGS],
)

function_op(
    name="builtins.len",
    arg_types=[bytes_writer_rprimitive],
    return_type=short_int_rprimitive,
    c_function_name="CPyBytesWriter_Len",
    error_kind=ERR_NEVER,
    experimental=True,
    dependencies=[LIBRT_STRINGS, BYTES_WRITER_EXTRA_OPS],
)

# BytesWriter index adjustment - convert negative index to positive
bytes_writer_adjust_index_op = custom_primitive_op(
    name="bytes_writer_adjust_index",
    arg_types=[bytes_writer_rprimitive, int64_rprimitive],
    return_type=int64_rprimitive,
    c_function_name="CPyBytesWriter_AdjustIndex",
    error_kind=ERR_NEVER,
    experimental=True,
    dependencies=[LIBRT_STRINGS, BYTES_WRITER_EXTRA_OPS],
)

# BytesWriter range check - check if index is in valid range
bytes_writer_range_check_op = custom_primitive_op(
    name="bytes_writer_range_check",
    arg_types=[bytes_writer_rprimitive, int64_rprimitive],
    return_type=bool_rprimitive,
    c_function_name="CPyBytesWriter_RangeCheck",
    error_kind=ERR_NEVER,
    experimental=True,
    dependencies=[LIBRT_STRINGS, BYTES_WRITER_EXTRA_OPS],
)

# BytesWriter.__getitem__() - get byte at index (no bounds checking)
bytes_writer_get_item_unsafe_op = custom_primitive_op(
    name="bytes_writer_get_item",
    arg_types=[bytes_writer_rprimitive, int64_rprimitive],
    return_type=uint8_rprimitive,
    c_function_name="CPyBytesWriter_GetItem",
    error_kind=ERR_NEVER,
    experimental=True,
    dependencies=[LIBRT_STRINGS, BYTES_WRITER_EXTRA_OPS],
)

# BytesWriter.__setitem__() - set byte at index (no bounds checking)
bytes_writer_set_item_unsafe_op = custom_primitive_op(
    name="bytes_writer_set_item",
    arg_types=[bytes_writer_rprimitive, int64_rprimitive, uint8_rprimitive],
    return_type=void_rtype,
    c_function_name="CPyBytesWriter_SetItem",
    error_kind=ERR_NEVER,
    experimental=True,
    dependencies=[LIBRT_STRINGS, BYTES_WRITER_EXTRA_OPS],
)
