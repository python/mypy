from mypyc.ir.deps import LIBRT_VECS, VECS_EXTRA_OPS
from mypyc.ir.ops import ERR_MAGIC, ERR_NEVER
from mypyc.ir.rtypes import (
    RTypeVar,
    RVec,
    bit_rprimitive,
    bytes_rprimitive,
    int64_rprimitive,
    object_rprimitive,
    uint8_rprimitive,
)
from mypyc.primitives.registry import custom_primitive_op, function_op

# isinstance(obj, vec)
isinstance_vec = function_op(
    name="builtins.isinstance",
    arg_types=[object_rprimitive],
    return_type=bit_rprimitive,
    c_function_name="CPyVec_Check",
    error_kind=ERR_NEVER,
    dependencies=[LIBRT_VECS, VECS_EXTRA_OPS],
)

# bytes(vec[u8])
function_op(
    name="builtins.bytes",
    arg_types=[RVec(uint8_rprimitive)],
    return_type=bytes_rprimitive,
    c_function_name="CPyVecU8_ToBytes",
    error_kind=ERR_MAGIC,
    dependencies=[LIBRT_VECS, VECS_EXTRA_OPS],
)

# Get vec item, assuming the index is valid (no bounds check)
vec_get_item_unsafe_op = custom_primitive_op(
    name="vec_get_item_unsafe",
    arg_types=[RVec(RTypeVar(0)), int64_rprimitive],
    return_type=RTypeVar(0),
    error_kind=ERR_NEVER,
    type_params=[RTypeVar(0)],
)

# Like vec_get_item_unsafe, but the result is a borrowed reference
vec_get_item_unsafe_borrow_op = custom_primitive_op(
    name="vec_get_item_unsafe_borrow",
    arg_types=[RVec(RTypeVar(0)), int64_rprimitive],
    is_borrowed=True,
    return_type=RTypeVar(0),
    error_kind=ERR_NEVER,
    type_params=[RTypeVar(0)],
)
