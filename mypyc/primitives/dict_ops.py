"""Primitive dict ops."""

from typing import List
from mypyc.ir.ops import ERR_FALSE, ERR_MAGIC, ERR_NEVER, Integer, Value, CallC
from mypyc.ir.rtypes import (
    RType, dict_rprimitive, int32_rprimitive, object_rprimitive, bool_rprimitive, int_rprimitive,
    list_rprimitive, dict_next_rtuple_single, dict_next_rtuple_pair, c_pyssize_t_rprimitive,
    c_int_rprimitive, bit_rprimitive
)

from mypyc.primitives.registry import (
    COERCER, custom_op, method_op, function_op, binary_op, load_address_op, ERR_NEG_INT, default_match
)

# Get the 'dict' type object.
load_address_op(
    name='builtins.dict',
    type=object_rprimitive,
    src='PyDict_Type')

# Construct an empty dictionary.
dict_new_op = custom_op(
    arg_types=[],
    return_type=dict_rprimitive,
    c_function_name='PyDict_New',
    error_kind=ERR_MAGIC)

# Construct a dictionary from keys and values.
# Positional argument is the number of key-value pairs
# Variable arguments are (key1, value1, ..., keyN, valueN).
dict_build_op = custom_op(
    arg_types=[c_pyssize_t_rprimitive],
    return_type=dict_rprimitive,
    c_function_name='CPyDict_Build',
    error_kind=ERR_MAGIC,
    var_arg_type=object_rprimitive)

# Construct a dictionary from another dictionary.
function_op(
    name='builtins.dict',
    arg_types=[dict_rprimitive],
    return_type=dict_rprimitive,
    c_function_name='PyDict_Copy',
    error_kind=ERR_MAGIC,
    priority=2)

# Generic one-argument dict constructor: dict(obj)
function_op(
    name='builtins.dict',
    arg_types=[object_rprimitive],
    return_type=dict_rprimitive,
    c_function_name='CPyDict_FromAny',
    error_kind=ERR_MAGIC)

# dict[key]
dict_get_item_op = method_op(
    name='__getitem__',
    arg_types=[dict_rprimitive, object_rprimitive],
    return_type=object_rprimitive,
    c_function_name='CPyDict_GetItem',
    error_kind=ERR_MAGIC)

# dict[key] = value
dict_set_item_op = method_op(
    name='__setitem__',
    arg_types=[dict_rprimitive, object_rprimitive, object_rprimitive],
    return_type=c_int_rprimitive,
    c_function_name='CPyDict_SetItem',
    error_kind=ERR_NEG_INT)

# key in dict
binary_op(
    name='in',
    arg_types=[object_rprimitive, dict_rprimitive],
    return_type=c_int_rprimitive,
    c_function_name='PyDict_Contains',
    error_kind=ERR_NEG_INT,
    truncated_type=bool_rprimitive,
    ordering=[1, 0])

# dict1.update(dict2)
dict_update_op = method_op(
    name='update',
    arg_types=[dict_rprimitive, dict_rprimitive],
    return_type=c_int_rprimitive,
    c_function_name='CPyDict_Update',
    error_kind=ERR_NEG_INT,
    priority=2)

# Operation used for **value in dict displays.
# This is mostly like dict.update(obj), but has customized error handling.
dict_update_in_display_op = custom_op(
    arg_types=[dict_rprimitive, dict_rprimitive],
    return_type=c_int_rprimitive,
    c_function_name='CPyDict_UpdateInDisplay',
    error_kind=ERR_NEG_INT)

# dict.update(obj)
method_op(
    name='update',
    arg_types=[dict_rprimitive, object_rprimitive],
    return_type=c_int_rprimitive,
    c_function_name='CPyDict_UpdateFromAny',
    error_kind=ERR_NEG_INT)

# dict.get(key, default)
method_op(
    name='get',
    arg_types=[dict_rprimitive, object_rprimitive, object_rprimitive],
    return_type=object_rprimitive,
    c_function_name='CPyDict_Get',
    error_kind=ERR_MAGIC)

# dict.get(key)
method_op(
    name='get',
    arg_types=[dict_rprimitive, object_rprimitive],
    return_type=object_rprimitive,
    c_function_name='CPyDict_GetWithNone',
    error_kind=ERR_MAGIC)

# dict.setdefault(key, {}) or dict.setdefault(key, []) or dict.setdefault(key, set())
def _setdefault_empty_match(desc_arg_types: List[RType], args: List[Value]):
    if not default_match(desc_arg_types, args):
        return False
    if isinstance(args[2], CallC):
        # TODO: implement optimization for set
        if args[2].function_name == "PyList_New":
            if (len(args[2].args) == 1 and isinstance(args[2].args[0], Integer) and
                    args[2].args[0].value == 0):
                return True
        elif args[2].function_name == "PyDict_New":
            return True
    return False

def _setdefault_empty_create_args(args: List[Value], coercer: COERCER) -> List[Value]:
    # code should be consistent with CPyDict_SetDefaultWithEmptyCollection
    code_map = {
        "PyList_New": 0,
        "PyDict_New": 1,
        "PySet_New": 2
    }
    assert isinstance(args[2], CallC)
    enum_value = Integer(code_map[args[2].function_name], int32_rprimitive, args[2].line)
    key = coercer(args[1], object_rprimitive, args[1].line, False)
    return [args[0], key, enum_value]

method_op(
    name='setdefault',
    arg_types=[dict_rprimitive, object_rprimitive, object_rprimitive],
    return_type = object_rprimitive,
    c_function_name='CPyDict_SetDefaultWithEmptyCollection',
    is_borrowed=True,
    error_kind=ERR_MAGIC,
    priority=2,
    match=_setdefault_empty_match,
    arg_converter=_setdefault_empty_create_args)

# dict.setdefault(key, default)
method_op(
    name='setdefault',
    arg_types=[dict_rprimitive, object_rprimitive, object_rprimitive],
    return_type=object_rprimitive,
    c_function_name='CPyDict_SetDefault',
    is_borrowed=True,
    error_kind=ERR_MAGIC)

# dict.setdefault(key)
method_op(
    name='setdefault',
    arg_types=[dict_rprimitive, object_rprimitive],
    return_type=object_rprimitive,
    c_function_name='CPyDict_SetDefaultWithNone',
    is_borrowed=True,
    error_kind=ERR_MAGIC)

# dict.keys()
method_op(
    name='keys',
    arg_types=[dict_rprimitive],
    return_type=object_rprimitive,
    c_function_name='CPyDict_KeysView',
    error_kind=ERR_MAGIC)

# dict.values()
method_op(
    name='values',
    arg_types=[dict_rprimitive],
    return_type=object_rprimitive,
    c_function_name='CPyDict_ValuesView',
    error_kind=ERR_MAGIC)

# dict.items()
method_op(
    name='items',
    arg_types=[dict_rprimitive],
    return_type=object_rprimitive,
    c_function_name='CPyDict_ItemsView',
    error_kind=ERR_MAGIC)

# dict.clear()
method_op(
    name='clear',
    arg_types=[dict_rprimitive],
    return_type=bit_rprimitive,
    c_function_name='CPyDict_Clear',
    error_kind=ERR_FALSE)

# dict.copy()
method_op(
    name='copy',
    arg_types=[dict_rprimitive],
    return_type=dict_rprimitive,
    c_function_name='CPyDict_Copy',
    error_kind=ERR_MAGIC)

# list(dict.keys())
dict_keys_op = custom_op(
    arg_types=[dict_rprimitive],
    return_type=list_rprimitive,
    c_function_name='CPyDict_Keys',
    error_kind=ERR_MAGIC)

# list(dict.values())
dict_values_op = custom_op(
    arg_types=[dict_rprimitive],
    return_type=list_rprimitive,
    c_function_name='CPyDict_Values',
    error_kind=ERR_MAGIC)

# list(dict.items())
dict_items_op = custom_op(
    arg_types=[dict_rprimitive],
    return_type=list_rprimitive,
    c_function_name='CPyDict_Items',
    error_kind=ERR_MAGIC)

# PyDict_Next() fast iteration
dict_key_iter_op = custom_op(
    arg_types=[dict_rprimitive],
    return_type=object_rprimitive,
    c_function_name='CPyDict_GetKeysIter',
    error_kind=ERR_MAGIC)

dict_value_iter_op = custom_op(
    arg_types=[dict_rprimitive],
    return_type=object_rprimitive,
    c_function_name='CPyDict_GetValuesIter',
    error_kind=ERR_MAGIC)

dict_item_iter_op = custom_op(
    arg_types=[dict_rprimitive],
    return_type=object_rprimitive,
    c_function_name='CPyDict_GetItemsIter',
    error_kind=ERR_MAGIC)

dict_next_key_op = custom_op(
    arg_types=[object_rprimitive, int_rprimitive],
    return_type=dict_next_rtuple_single,
    c_function_name='CPyDict_NextKey',
    error_kind=ERR_NEVER)

dict_next_value_op = custom_op(
    arg_types=[object_rprimitive, int_rprimitive],
    return_type=dict_next_rtuple_single,
    c_function_name='CPyDict_NextValue',
    error_kind=ERR_NEVER)

dict_next_item_op = custom_op(
    arg_types=[object_rprimitive, int_rprimitive],
    return_type=dict_next_rtuple_pair,
    c_function_name='CPyDict_NextItem',
    error_kind=ERR_NEVER)

# check that len(dict) == const during iteration
dict_check_size_op = custom_op(
    arg_types=[dict_rprimitive, int_rprimitive],
    return_type=bit_rprimitive,
    c_function_name='CPyDict_CheckSize',
    error_kind=ERR_FALSE)

dict_size_op = custom_op(
    arg_types=[dict_rprimitive],
    return_type=c_pyssize_t_rprimitive,
    c_function_name='PyDict_Size',
    error_kind=ERR_NEVER)
