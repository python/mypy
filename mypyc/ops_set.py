"""Primitive set ops."""
from mypyc.ops_primitive import func_op, custom_op, simple_emit
from mypyc.ops import object_rprimitive, bool_rprimitive, ERR_MAGIC, ERR_FALSE

new_set_op = func_op(
    name='builtins.set',
    arg_types=[],
    result_type=object_rprimitive,
    error_kind=ERR_MAGIC,
    format_str='{dest} = set()',
    emit=simple_emit('{dest} = PySet_New(NULL);')
)

# This operation is only used during set literal generation. The first argument must be a set.
# If sets get added as special types, this will become a method_op on set rprimitives.
set_add_op = custom_op(
    arg_types=[object_rprimitive, object_rprimitive],
    result_type=bool_rprimitive,
    error_kind=ERR_FALSE,
    format_str='{dest} = {args[0]}.add({args[1]})',
    emit=simple_emit('{dest} = PySet_Add({args[0]}, {args[1]}) == 0;')
)
