"""Miscellaneous primitive ops."""

from mypyc.ir.ops import ERR_NEVER, ERR_MAGIC, ERR_FALSE
from mypyc.ir.rtypes import (
    RTuple, none_rprimitive, bool_rprimitive, object_rprimitive, str_rprimitive,
    int_rprimitive, dict_rprimitive
)
from mypyc.primitives.registry import (
    name_ref_op, simple_emit, unary_op, func_op, custom_op, call_emit, name_emit,
    call_negative_magic_emit
)


# Get the boxed Python 'None' object
none_object_op = custom_op(result_type=object_rprimitive,
                           arg_types=[],
                           error_kind=ERR_NEVER,
                           format_str='{dest} = builtins.None :: object',
                           emit=name_emit('Py_None'),
                           is_borrowed=True)

# Get an unboxed None value
none_op = name_ref_op('builtins.None',
                      result_type=none_rprimitive,
                      error_kind=ERR_NEVER,
                      emit=simple_emit('{dest} = 1; /* None */'))

# Get an unboxed True value
true_op = name_ref_op('builtins.True',
                      result_type=bool_rprimitive,
                      error_kind=ERR_NEVER,
                      emit=simple_emit('{dest} = 1;'))

# Get an unboxed False value
false_op = name_ref_op('builtins.False',
                       result_type=bool_rprimitive,
                       error_kind=ERR_NEVER,
                       emit=simple_emit('{dest} = 0;'))

# Get the boxed object '...'
ellipsis_op = custom_op(name='...',
                        arg_types=[],
                        result_type=object_rprimitive,
                        error_kind=ERR_NEVER,
                        emit=name_emit('Py_Ellipsis'),
                        is_borrowed=True)

# Get the boxed NotImplemented object
not_implemented_op = name_ref_op(name='builtins.NotImplemented',
                                 result_type=object_rprimitive,
                                 error_kind=ERR_NEVER,
                                 emit=name_emit('Py_NotImplemented'),
                                 is_borrowed=True)

# id(obj)
func_op(name='builtins.id',
        arg_types=[object_rprimitive],
        result_type=int_rprimitive,
        error_kind=ERR_NEVER,
        emit=call_emit('CPyTagged_Id'))

# Return the result of obj.__await()__ or obj.__iter__() (if no __await__ exists)
coro_op = custom_op(name='get_coroutine_obj',
                    arg_types=[object_rprimitive],
                    result_type=object_rprimitive,
                    error_kind=ERR_MAGIC,
                    emit=call_emit('CPy_GetCoro'))

# Do obj.send(value), or a next(obj) if second arg is None.
# (This behavior is to match the PEP 380 spec for yield from.)
# Like next_raw_op, don't swallow StopIteration,
# but also don't propagate an error.
# Can return NULL: see next_op.
send_op = custom_op(name='send',
                    arg_types=[object_rprimitive, object_rprimitive],
                    result_type=object_rprimitive,
                    error_kind=ERR_NEVER,
                    emit=call_emit('CPyIter_Send'))

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
method_new_op = custom_op(name='method_new',
                          arg_types=[object_rprimitive, object_rprimitive],
                          result_type=object_rprimitive,
                          error_kind=ERR_MAGIC,
                          emit=call_emit('PyMethod_New'))

# Check if the current exception is a StopIteration and return its value if so.
# Treats "no exception" as StopIteration with a None value.
# If it is a different exception, re-reraise it.
check_stop_op = custom_op(name='check_stop_iteration',
                          arg_types=[],
                          result_type=object_rprimitive,
                          error_kind=ERR_MAGIC,
                          emit=call_emit('CPy_FetchStopIterationValue'))

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
import_op = custom_op(
    name='import',
    arg_types=[str_rprimitive],
    result_type=object_rprimitive,
    error_kind=ERR_MAGIC,
    emit=call_emit('PyImport_Import'))

# Get the sys.modules dictionary
get_module_dict_op = custom_op(
    name='get_module_dict',
    arg_types=[],
    result_type=dict_rprimitive,
    error_kind=ERR_NEVER,
    emit=call_emit('PyImport_GetModuleDict'),
    is_borrowed=True)

# isinstance(obj, cls)
func_op('builtins.isinstance',
        arg_types=[object_rprimitive, object_rprimitive],
        result_type=bool_rprimitive,
        error_kind=ERR_MAGIC,
        emit=call_negative_magic_emit('PyObject_IsInstance'))

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
new_slice_op = func_op(
    'builtins.slice',
    arg_types=[object_rprimitive, object_rprimitive, object_rprimitive],
    result_type=object_rprimitive,
    error_kind=ERR_MAGIC,
    emit=call_emit('PySlice_New'))

# type(obj)
type_op = func_op(
    'builtins.type',
    arg_types=[object_rprimitive],
    result_type=object_rprimitive,
    error_kind=ERR_NEVER,
    emit=call_emit('PyObject_Type'))

# Get 'builtins.type' (base class of all classes)
type_object_op = name_ref_op(
    'builtins.type',
    result_type=object_rprimitive,
    error_kind=ERR_NEVER,
    emit=name_emit('&PyType_Type', target_type='PyObject *'),
    is_borrowed=True)

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
dataclass_sleight_of_hand = custom_op(
    arg_types=[object_rprimitive, object_rprimitive, dict_rprimitive, dict_rprimitive],
    result_type=bool_rprimitive,
    error_kind=ERR_FALSE,
    format_str='{dest} = dataclass_sleight_of_hand({comma_args})',
    emit=call_emit('CPyDataclass_SleightOfHand'))
