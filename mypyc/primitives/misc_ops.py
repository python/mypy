"""Miscellaneous primitive ops."""

from mypyc.ir.ops import ERR_NEVER, ERR_MAGIC, ERR_FALSE, ERR_NEG_INT
from mypyc.ir.rtypes import (
    RTuple, bool_rprimitive, object_rprimitive, str_rprimitive,
    int_rprimitive, dict_rprimitive, c_int_rprimitive
)
from mypyc.primitives.registry import (
    simple_emit, unary_op, func_op, custom_op, call_emit, name_emit,
    call_negative_magic_emit, c_function_op, c_custom_op, load_address_op
)


# Get the boxed Python 'None' object
none_object_op = custom_op(result_type=object_rprimitive,
                           arg_types=[],
                           error_kind=ERR_NEVER,
                           format_str='{dest} = builtins.None :: object',
                           emit=name_emit('Py_None'),
                           is_borrowed=True)


# Get the boxed object '...'
ellipsis_op = custom_op(name='...',
                        arg_types=[],
                        result_type=object_rprimitive,
                        error_kind=ERR_NEVER,
                        emit=name_emit('Py_Ellipsis'),
                        is_borrowed=True)

# Get the boxed NotImplemented object
not_implemented_op = load_address_op(
    name='builtins.NotImplemented',
    type=object_rprimitive,
    src='_Py_NotImplementedStruct')

# id(obj)
c_function_op(
    name='builtins.id',
    arg_types=[object_rprimitive],
    return_type=int_rprimitive,
    c_function_name='CPyTagged_Id',
    error_kind=ERR_NEVER)

# Return the result of obj.__await()__ or obj.__iter__() (if no __await__ exists)
coro_op = c_custom_op(
    arg_types=[object_rprimitive],
    return_type=object_rprimitive,
    c_function_name='CPy_GetCoro',
    error_kind=ERR_MAGIC)

# Do obj.send(value), or a next(obj) if second arg is None.
# (This behavior is to match the PEP 380 spec for yield from.)
# Like next_raw_op, don't swallow StopIteration,
# but also don't propagate an error.
# Can return NULL: see next_op.
send_op = c_custom_op(
    arg_types=[object_rprimitive, object_rprimitive],
    return_type=object_rprimitive,
    c_function_name='CPyIter_Send',
    error_kind=ERR_NEVER)

# This is sort of unfortunate but oh well: yield_from_except performs most of the
# error handling logic in `yield from` operations. It returns a bool and a value.
# If the bool is true, then a StopIteration was received and we should return.
# If the bool is false, then the value should be yielded.
# The normal case is probably that it signals an exception, which gets
# propagated.
yield_from_rtuple = RTuple([bool_rprimitive, object_rprimitive])

# Op used for "yield from" error handling.
# See comment in CPy_YieldFromErrorHandle for more information.
yield_from_except_op = custom_op(
    name='yield_from_except',
    arg_types=[object_rprimitive],
    result_type=yield_from_rtuple,
    error_kind=ERR_MAGIC,
    emit=simple_emit('{dest}.f0 = CPy_YieldFromErrorHandle({args[0]}, &{dest}.f1);'))

# Create method object from a callable object and self.
method_new_op = c_custom_op(
    arg_types=[object_rprimitive, object_rprimitive],
    return_type=object_rprimitive,
    c_function_name='PyMethod_New',
    error_kind=ERR_MAGIC)

# Check if the current exception is a StopIteration and return its value if so.
# Treats "no exception" as StopIteration with a None value.
# If it is a different exception, re-reraise it.
check_stop_op = c_custom_op(
    arg_types=[],
    return_type=object_rprimitive,
    c_function_name='CPy_FetchStopIterationValue',
    error_kind=ERR_MAGIC)

# Negate a primitive bool
unary_op(op='not',
         arg_type=bool_rprimitive,
         result_type=bool_rprimitive,
         error_kind=ERR_NEVER,
         format_str='{dest} = !{args[0]}',
         emit=simple_emit('{dest} = !{args[0]};'),
         priority=1)

# Determine the most derived metaclass and check for metaclass conflicts.
# Arguments are (metaclass, bases).
py_calc_meta_op = custom_op(
    arg_types=[object_rprimitive, object_rprimitive],
    result_type=object_rprimitive,
    error_kind=ERR_MAGIC,
    format_str='{dest} = py_calc_metaclass({comma_args})',
    emit=simple_emit(
        '{dest} = (PyObject*) _PyType_CalculateMetaclass((PyTypeObject *){args[0]}, {args[1]});'),
    is_borrowed=True
)

# Import a module
import_op = c_custom_op(
    arg_types=[str_rprimitive],
    return_type=object_rprimitive,
    c_function_name='PyImport_Import',
    error_kind=ERR_MAGIC)

# Get the sys.modules dictionary
get_module_dict_op = custom_op(
    name='get_module_dict',
    arg_types=[],
    result_type=dict_rprimitive,
    error_kind=ERR_NEVER,
    emit=call_emit('PyImport_GetModuleDict'),
    is_borrowed=True)

# isinstance(obj, cls)
c_function_op(
    name='builtins.isinstance',
    arg_types=[object_rprimitive, object_rprimitive],
    return_type=c_int_rprimitive,
    c_function_name='PyObject_IsInstance',
    error_kind=ERR_NEG_INT,
    truncated_type=bool_rprimitive
)

# Faster isinstance(obj, cls) that only works with native classes and doesn't perform
# type checking of the type argument.
fast_isinstance_op = func_op(
    'builtins.isinstance',
    arg_types=[object_rprimitive, object_rprimitive],
    result_type=bool_rprimitive,
    error_kind=ERR_NEVER,
    emit=simple_emit('{dest} = PyObject_TypeCheck({args[0]}, (PyTypeObject *){args[1]});'),
    priority=0)

# Exact type check that doesn't consider subclasses: type(obj) is cls
type_is_op = custom_op(
    name='type_is',
    arg_types=[object_rprimitive, object_rprimitive],
    result_type=bool_rprimitive,
    error_kind=ERR_NEVER,
    emit=simple_emit('{dest} = Py_TYPE({args[0]}) == (PyTypeObject *){args[1]};'))

# bool(obj) with unboxed result
bool_op = func_op(
    'builtins.bool',
    arg_types=[object_rprimitive],
    result_type=bool_rprimitive,
    error_kind=ERR_MAGIC,
    emit=call_negative_magic_emit('PyObject_IsTrue'))

# slice(start, stop, step)
new_slice_op = c_function_op(
    name='builtins.slice',
    arg_types=[object_rprimitive, object_rprimitive, object_rprimitive],
    c_function_name='PySlice_New',
    return_type=object_rprimitive,
    error_kind=ERR_MAGIC)

# type(obj)
type_op = c_function_op(
    name='builtins.type',
    arg_types=[object_rprimitive],
    c_function_name='PyObject_Type',
    return_type=object_rprimitive,
    error_kind=ERR_NEVER)

# Get 'builtins.type' (base class of all classes)
type_object_op = load_address_op(
    name='builtins.type',
    type=object_rprimitive,
    src='PyType_Type')

# Create a heap type based on a template non-heap type.
# See CPyType_FromTemplate for more docs.
pytype_from_template_op = custom_op(
    arg_types=[object_rprimitive, object_rprimitive, str_rprimitive],
    result_type=object_rprimitive,
    error_kind=ERR_MAGIC,
    format_str='{dest} = pytype_from_template({comma_args})',
    emit=simple_emit(
        '{dest} = CPyType_FromTemplate((PyTypeObject *){args[0]}, {args[1]}, {args[2]});'))

# Create a dataclass from an extension class. See
# CPyDataclass_SleightOfHand for more docs.
dataclass_sleight_of_hand = c_custom_op(
    arg_types=[object_rprimitive, object_rprimitive, dict_rprimitive, dict_rprimitive],
    return_type=bool_rprimitive,
    c_function_name='CPyDataclass_SleightOfHand',
    error_kind=ERR_FALSE)
