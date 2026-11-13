"""Primitive tuple ops for *variable-length* tuples.

Note: Varying-length tuples are represented as boxed Python tuple
objects, i.e. tuple_rprimitive (RPrimitive), not RTuple.
"""

from __future__ import annotations

from mypyc.ir.ops import ERR_MAGIC, ERR_NEVER
from mypyc.ir.rtypes import (
    bit_rprimitive,
    c_pyssize_t_rprimitive,
    c_size_t_rprimitive,
    int_rprimitive,
    list_rprimitive,
    object_rprimitive,
    tuple_rprimitive,
    void_rtype,
)
from mypyc.primitives.registry import binary_op, custom_op, function_op, load_address_op, method_op

# Get the 'builtins.tuple' type object.
load_address_op(name="builtins.tuple", type=object_rprimitive, src="PyTuple_Type")

# tuple[index] (for an int index)
tuple_get_item_op = method_op(
    name="__getitem__",
    arg_types=[tuple_rprimitive, int_rprimitive],
    return_type=object_rprimitive,
    c_function_name="CPySequenceTuple_GetItem",
    error_kind=ERR_MAGIC,
)

# This is unsafe because it assumes that the index is a non-negative integer
# that is in-bounds for the tuple.
tuple_get_item_unsafe_op = custom_op(
    arg_types=[tuple_rprimitive, c_pyssize_t_rprimitive],
    return_type=object_rprimitive,
    c_function_name="CPySequenceTuple_GetItemUnsafe",
    error_kind=ERR_NEVER,
)

# Construct a boxed tuple from items: (item1, item2, ...)
new_tuple_op = custom_op(
    arg_types=[c_pyssize_t_rprimitive],
    return_type=tuple_rprimitive,
    c_function_name="PyTuple_Pack",
    error_kind=ERR_MAGIC,
    var_arg_type=object_rprimitive,
)

new_tuple_with_length_op = custom_op(
    arg_types=[c_pyssize_t_rprimitive],
    return_type=tuple_rprimitive,
    c_function_name="PyTuple_New",
    error_kind=ERR_MAGIC,
)

load_empty_tuple_constant_op = custom_op(
    arg_types=[],
    return_type=tuple_rprimitive,
    c_function_name="CPyTuple_LoadEmptyTupleConstant",
    error_kind=ERR_NEVER,
)

# PyTuple_SET_ITEM does no error checking,
# and should only be used to fill in brand new tuples.
new_tuple_set_item_op = custom_op(
    arg_types=[tuple_rprimitive, c_pyssize_t_rprimitive, object_rprimitive],
    return_type=void_rtype,
    c_function_name="CPySequenceTuple_SetItemUnsafe",
    error_kind=ERR_NEVER,
    steals=[False, False, True],
)

# Like new_tuple_set_item_op, but grow the tuple if the index is out of range.
# Items before the index must have been set. Returns the resulting tuple.
new_tuple_set_item_grow_op = custom_op(
    arg_types=[tuple_rprimitive, c_pyssize_t_rprimitive, object_rprimitive],
    return_type=tuple_rprimitive,
    c_function_name="CPySequenceTuple_SetItemGrow",
    error_kind=ERR_MAGIC,
    steals=[True, False, True],
)

# Set the size of a tuple built using new_tuple_set_item_op or new_tuple_set_item_grow_op.
# Items before the new size must have been set, and items after it must not have been set.
# Returns the resulting tuple.
new_tuple_set_size_op = custom_op(
    arg_types=[tuple_rprimitive, c_pyssize_t_rprimitive],
    return_type=tuple_rprimitive,
    c_function_name="CPySequenceTuple_SetSize",
    error_kind=ERR_MAGIC,
    steals=[True, False],
)

# Construct tuple from a list.
list_tuple_op = function_op(
    name="builtins.tuple",
    arg_types=[list_rprimitive],
    return_type=tuple_rprimitive,
    c_function_name="PyList_AsTuple",
    error_kind=ERR_MAGIC,
    priority=2,
)

# Construct tuple from an arbitrary (iterable) object.
sequence_tuple_op = function_op(
    name="builtins.tuple",
    arg_types=[object_rprimitive],
    return_type=tuple_rprimitive,
    c_function_name="PySequence_Tuple",
    error_kind=ERR_MAGIC,
)

# translate isinstance(obj, tuple)
isinstance_tuple = function_op(
    name="builtins.isinstance",
    arg_types=[object_rprimitive],
    return_type=bit_rprimitive,
    c_function_name="PyTuple_Check",
    error_kind=ERR_NEVER,
)

# tuple + tuple
binary_op(
    name="+",
    arg_types=[tuple_rprimitive, tuple_rprimitive],
    return_type=tuple_rprimitive,
    c_function_name="CPySequence_Concat",
    error_kind=ERR_MAGIC,
)

# tuple * int
binary_op(
    name="*",
    arg_types=[tuple_rprimitive, int_rprimitive],
    return_type=tuple_rprimitive,
    c_function_name="CPySequence_Multiply",
    error_kind=ERR_MAGIC,
)

# int * tuple
binary_op(
    name="*",
    arg_types=[int_rprimitive, tuple_rprimitive],
    return_type=tuple_rprimitive,
    c_function_name="CPySequence_RMultiply",
    error_kind=ERR_MAGIC,
)

# tuple[begin:end]
tuple_slice_op = custom_op(
    arg_types=[tuple_rprimitive, int_rprimitive, int_rprimitive],
    return_type=object_rprimitive,
    c_function_name="CPySequenceTuple_GetSlice",
    error_kind=ERR_MAGIC,
)

# The steps of hash() for a fixed-length tuple (RTuple), which combine the C hashes
# of its items without building a tuple object (see CPyTupleHash_Start in CPy.h)
tuple_hash_start_op = custom_op(
    arg_types=[],
    return_type=c_size_t_rprimitive,
    c_function_name="CPyTupleHash_Start",
    error_kind=ERR_NEVER,
)

tuple_hash_add_op = custom_op(
    arg_types=[c_size_t_rprimitive, c_pyssize_t_rprimitive],
    return_type=c_size_t_rprimitive,
    c_function_name="CPyTupleHash_Add",
    error_kind=ERR_NEVER,
)

tuple_hash_finish_op = custom_op(
    arg_types=[c_size_t_rprimitive, c_pyssize_t_rprimitive],
    return_type=c_pyssize_t_rprimitive,
    c_function_name="CPyTupleHash_Finish",
    error_kind=ERR_NEVER,
)

# The C hash of an int item
tuple_hash_int_op = custom_op(
    arg_types=[int_rprimitive],
    return_type=c_pyssize_t_rprimitive,
    c_function_name="CPyTupleHash_Int",
    error_kind=ERR_NEVER,
)

# The C hash of any other item, which is -1 on error (the caller checks for it)
tuple_hash_object_op = custom_op(
    arg_types=[object_rprimitive],
    return_type=c_pyssize_t_rprimitive,
    c_function_name="PyObject_Hash",
    error_kind=ERR_NEVER,
)
