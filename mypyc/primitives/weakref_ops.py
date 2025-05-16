from mypyc.ir.rtypes import object_rprimitive
from mypyc.primitives.registry import function_op

# Weakref operations

"""
py_new_weak_ref_op = function_op(
    name="weakref.weakref",
    arg_types=[object_rprimitive],
    # TODO: how do I pass NULL as the 2nd arg? 
    #extra_int_constants=[],
    result_type=object_rprimitive,
    c_function_name="PyWeakref_NewRef",
)
"""

py_new_weak_ref_with_callback_op = function_op(
    name="weakref.weakref",
    arg_types=[object_rprimitive, object_rprimitive],
    result_type=object_rprimitive,
    c_function_name="PyWeakref_NewRef",
)

"""
py_new_weak_proxy_op = function_op(
    name="weakref.proxy",
    arg_types=[object_rprimitive],
    result_type=object_rprimitive,
    c_function_name="PyWeakref_NewProxy",
)
"""

py_new_weak_proxy_with_callback_op = function_op(
    name="weakref.proxy",
    arg_types=[object_rprimitive, object_rprimitive],
    result_type=object_rprimitive,
    c_function_name="PyWeakref_NewProxy",
)
