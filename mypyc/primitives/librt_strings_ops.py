from typing import Final

from mypyc.ir.ops import ERR_MAGIC, ERR_NEVER
from mypyc.ir.rtypes import (
    KNOWN_NATIVE_TYPES,
    bytes_rprimitive,
    int64_rprimitive,
    none_rprimitive,
    short_int_rprimitive,
    uint8_rprimitive,
)
from mypyc.primitives.registry import function_op, method_op

bytes_writer_rprimitive: Final = KNOWN_NATIVE_TYPES["librt.strings.BytesWriter"]

function_op(
    name="librt.strings.BytesWriter",
    arg_types=[],
    return_type=bytes_writer_rprimitive,
    c_function_name="LibRTStrings_BytesWriter_internal",
    error_kind=ERR_MAGIC,
    experimental=True,
    capsule="librt.strings",
)

method_op(
    name="getvalue",
    arg_types=[bytes_writer_rprimitive],
    return_type=bytes_rprimitive,
    c_function_name="LibRTStrings_BytesWriter_getvalue_internal",
    error_kind=ERR_MAGIC,
    experimental=True,
    capsule="librt.strings",
)

method_op(
    name="write",
    arg_types=[bytes_writer_rprimitive, bytes_rprimitive],
    return_type=none_rprimitive,
    c_function_name="LibRTStrings_BytesWriter_write_internal",
    error_kind=ERR_MAGIC,
    experimental=True,
    capsule="librt.strings",
)

method_op(
    name="append",
    arg_types=[bytes_writer_rprimitive, uint8_rprimitive],
    return_type=none_rprimitive,
    c_function_name="LibRTStrings_BytesWriter_append_internal",
    error_kind=ERR_MAGIC,
    experimental=True,
    capsule="librt.strings",
)

method_op(
    name="truncate",
    arg_types=[bytes_writer_rprimitive, int64_rprimitive],
    return_type=none_rprimitive,
    c_function_name="LibRTStrings_BytesWriter_truncate_internal",
    error_kind=ERR_MAGIC,
)

function_op(
    name="builtins.len",
    arg_types=[bytes_writer_rprimitive],
    return_type=short_int_rprimitive,
    c_function_name="LibRTStrings_BytesWriter_len_internal",
    error_kind=ERR_NEVER,
    experimental=True,
    capsule="librt.strings",
)
