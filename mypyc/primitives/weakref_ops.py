from mypyc.ir.ops import ERR_MAGIC
from mypyc.ir.rtypes import object_rprimitive
from mypyc.primitives.registry import ERR_NEG_INT, function_op

# Weakref operations

new_ref_op = function_op(
    name="weakref.ReferenceType",
    arg_types=[object_rprimitive, object_rprimitive],
    return_type=object_rprimitive,
    c_function_name="PyWeakref_NewRef",
    error_kind=ERR_MAGIC,
)

deref_op = function_op(
    name="weakref.ReferenceType.__call__",
    arg_types=[object_rprimitive],
    return_type=object_rprimitive,
    c_function_name="PyWeakref_GetRef",
    error_kind=ERR_NEG_INT,
)
