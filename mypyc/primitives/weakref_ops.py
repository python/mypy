from mypyc.ir.ops import ERR_MAGIC
from mypyc.ir.rtypes import object_rprimitive, pointer_rprimitive, weakref_rprimitive
from mypyc.primitives.registry import ERR_NEG_INT, function_op, method_op

# Weakref operations

new_ref_op = function_op(
    name="weakref.ReferenceType",
    arg_types=[object_rprimitive],
    return_type=weakref_rprimitive,
    c_function_name="PyWeakref_NewRef",
    extra_int_constants=[(0, pointer_rprimitive)],
    error_kind=ERR_MAGIC,
)

new_ref__with_callback_op = function_op(
    name="weakref.ReferenceType",
    arg_types=[object_rprimitive, object_rprimitive],
    return_type=weakref_rprimitive,
    c_function_name="PyWeakref_NewRef",
    error_kind=ERR_MAGIC,
)

deref_op = method_op(
    name="__call__",
    arg_types=[weakref_rprimitive],
    return_type=object_rprimitive,
    c_function_name="PyWeakref_GetRef",
    error_kind=ERR_NEG_INT,
)
