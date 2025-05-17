from mypyc.ir.rtypes import object_rprimitive
from mypyc.primitives.registry import function_op

# Weakref operations

py_weakref_new_ref_op = function_op(
    name="weakref.weakref",
    arg_types=[object_rprimitive, object_rprimitive],
    return_type=object_rprimitive,
    c_function_name="PyWeakref_NewRef",
)

py_weakref_new_ref_op = function_op(
    name="weakref.proxy",
    arg_types=[object_rprimitive, object_rprimitive],
    return_type=object_rprimitive,
    c_function_name="PyWeakref_NewProxy",
)
