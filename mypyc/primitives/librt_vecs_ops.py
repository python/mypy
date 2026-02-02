from mypyc.ir.deps import LIBRT_VECS, VECS_EXTRA_OPS
from mypyc.ir.ops import ERR_NEVER
from mypyc.ir.rtypes import bit_rprimitive, object_rprimitive
from mypyc.primitives.registry import function_op

# isinstance(obj, vec)
isinstance_vec = function_op(
    name="builtins.isinstance",
    arg_types=[object_rprimitive],
    return_type=bit_rprimitive,
    c_function_name="CPyVec_Check",
    error_kind=ERR_NEVER,
    experimental=True,
    dependencies=[LIBRT_VECS, VECS_EXTRA_OPS],
)
