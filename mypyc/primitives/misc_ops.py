"""Miscellaneous primitive ops."""


from mypyc.ir.ops import ERR_NEVER, ERR_MAGIC, ERR_FALSE
from mypyc.ir.rtypes import (
    RTuple, none_rprimitive, bool_rprimitive, object_rprimitive, str_rprimitive,
    int_rprimitive, dict_rprimitive
)
from mypyc.primitives.registry import (
    name_ref_op, simple_emit, binary_op, unary_op, func_op, method_op, custom_op,
    negative_int_emit,
    call_emit, name_emit, call_negative_bool_emit, call_negative_magic_emit,
)


none_object_op = custom_op(result_type=object_rprimitive,
                           arg_types=[],
                           error_kind=ERR_NEVER,
                           format_str='{dest} = builtins.None :: object',
                           emit=name_emit('Py_None'),
                           is_borrowed=True)

none_op = name_ref_op('builtins.None',
                      result_type=none_rprimitive,
                      error_kind=ERR_NEVER,
                      emit=simple_emit('{dest} = 1; /* None */'))

true_op = name_ref_op('builtins.True',
                      result_type=bool_rprimitive,
                      error_kind=ERR_NEVER,
                      emit=simple_emit('{dest} = 1;'))

false_op = name_ref_op('builtins.False',
                       result_type=bool_rprimitive,
                       error_kind=ERR_NEVER,
                       emit=simple_emit('{dest} = 0;'))

ellipsis_op = custom_op(name='...',
                        arg_types=[],
                        result_type=object_rprimitive,
                        error_kind=ERR_NEVER,
                        emit=name_emit('Py_Ellipsis'),
                        is_borrowed=True)

not_implemented_op = name_ref_op(name='builtins.NotImplemented',
                                 result_type=object_rprimitive,
                                 error_kind=ERR_NEVER,
                                 emit=name_emit('Py_NotImplemented'),
                                 is_borrowed=True)

func_op(name='builtins.id',
        arg_types=[object_rprimitive],
        result_type=int_rprimitive,
        error_kind=ERR_NEVER,
        emit=call_emit('CPyTagged_Id'))

iter_op = func_op(name='builtins.iter',
                  arg_types=[object_rprimitive],
                  result_type=object_rprimitive,
                  error_kind=ERR_MAGIC,
                  emit=call_emit('PyObject_GetIter'))

coro_op = custom_op(name='get_coroutine_obj',
                    arg_types=[object_rprimitive],
                    result_type=object_rprimitive,
                    error_kind=ERR_MAGIC,
                    emit=call_emit('CPy_GetCoro'))

# Although the error_kind is set to be ERR_NEVER, this can actually
# return NULL, and thus it must be checked using Branch.IS_ERROR.
next_op = custom_op(name='next',
                    arg_types=[object_rprimitive],
                    result_type=object_rprimitive,
                    error_kind=ERR_NEVER,
                    emit=call_emit('PyIter_Next'))

# Do a next, don't swallow StopIteration, but also don't propagate an
# error. (N.B: This can still return NULL without an error to
# represent an implicit StopIteration, but if StopIteration is
# *explicitly* raised this will not swallow it.)
# Can return NULL: see next_op.
next_raw_op = custom_op(name='next',
                        arg_types=[object_rprimitive],
                        result_type=object_rprimitive,
                        error_kind=ERR_NEVER,
                        emit=call_emit('CPyIter_Next'))

# Do a send, or a next if second arg is None.
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

yield_from_except_op = custom_op(
    name='yield_from_except',
    arg_types=[object_rprimitive],
    result_type=yield_from_rtuple,
    error_kind=ERR_MAGIC,
    emit=simple_emit('{dest}.f0 = CPy_YieldFromErrorHandle({args[0]}, &{dest}.f1);'))


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


#
# Fallback primitive operations that operate on 'object' operands
#

for op, opid in [('==', 'Py_EQ'),
                 ('!=', 'Py_NE'),
                 ('<', 'Py_LT'),
                 ('<=', 'Py_LE'),
                 ('>', 'Py_GT'),
                 ('>=', 'Py_GE')]:
    # The result type is 'object' since that's what PyObject_RichCompare returns.
    binary_op(op=op,
              arg_types=[object_rprimitive, object_rprimitive],
              result_type=object_rprimitive,
              error_kind=ERR_MAGIC,
              emit=simple_emit('{dest} = PyObject_RichCompare({args[0]}, {args[1]}, %s);' % opid),
              priority=0)

for op, funcname in [('+', 'PyNumber_Add'),
                     ('-', 'PyNumber_Subtract'),
                     ('*', 'PyNumber_Multiply'),
                     ('//', 'PyNumber_FloorDivide'),
                     ('/', 'PyNumber_TrueDivide'),
                     ('%', 'PyNumber_Remainder'),
                     ('<<', 'PyNumber_Lshift'),
                     ('>>', 'PyNumber_Rshift'),
                     ('&', 'PyNumber_And'),
                     ('^', 'PyNumber_Xor'),
                     ('|', 'PyNumber_Or')]:
    binary_op(op=op,
              arg_types=[object_rprimitive, object_rprimitive],
              result_type=object_rprimitive,
              error_kind=ERR_MAGIC,
              emit=call_emit(funcname),
              priority=0)

for op, funcname in [('+=', 'PyNumber_InPlaceAdd'),
                     ('-=', 'PyNumber_InPlaceSubtract'),
                     ('*=', 'PyNumber_InPlaceMultiply'),
                     ('@=', 'PyNumber_InPlaceMatrixMultiply'),
                     ('//=', 'PyNumber_InPlaceFloorDivide'),
                     ('/=', 'PyNumber_InPlaceTrueDivide'),
                     ('%=', 'PyNumber_InPlaceRemainder'),
                     ('<<=', 'PyNumber_InPlaceLshift'),
                     ('>>=', 'PyNumber_InPlaceRshift'),
                     ('&=', 'PyNumber_InPlaceAnd'),
                     ('^=', 'PyNumber_InPlaceXor'),
                     ('|=', 'PyNumber_InPlaceOr')]:
    binary_op(op=op,
              arg_types=[object_rprimitive, object_rprimitive],
              result_type=object_rprimitive,
              error_kind=ERR_MAGIC,
              emit=simple_emit('{dest} = %s({args[0]}, {args[1]});' % funcname),
              priority=0)

binary_op(op='**',
          arg_types=[object_rprimitive, object_rprimitive],
          result_type=object_rprimitive,
          error_kind=ERR_MAGIC,
          emit=simple_emit('{dest} = PyNumber_Power({args[0]}, {args[1]}, Py_None);'),
          priority=0)

binary_op('in',
          arg_types=[object_rprimitive, object_rprimitive],
          result_type=bool_rprimitive,
          error_kind=ERR_MAGIC,
          emit=negative_int_emit('{dest} = PySequence_Contains({args[1]}, {args[0]});'),
          priority=0)

binary_op('is',
          arg_types=[object_rprimitive, object_rprimitive],
          result_type=bool_rprimitive,
          error_kind=ERR_NEVER,
          emit=simple_emit('{dest} = {args[0]} == {args[1]};'),
          priority=0)

binary_op('is not',
          arg_types=[object_rprimitive, object_rprimitive],
          result_type=bool_rprimitive,
          error_kind=ERR_NEVER,
          emit=simple_emit('{dest} = {args[0]} != {args[1]};'),
          priority=0)

for op, funcname in [('-', 'PyNumber_Negative'),
                     ('+', 'PyNumber_Positive'),
                     ('~', 'PyNumber_Invert')]:
    unary_op(op=op,
             arg_type=object_rprimitive,
             result_type=object_rprimitive,
             error_kind=ERR_MAGIC,
             emit=call_emit(funcname),
             priority=0)

unary_op(op='not',
         arg_type=object_rprimitive,
         result_type=bool_rprimitive,
         error_kind=ERR_MAGIC,
         format_str='{dest} = not {args[0]}',
         emit=call_negative_magic_emit('PyObject_Not'),
         priority=0)

unary_op(op='not',
         arg_type=bool_rprimitive,
         result_type=bool_rprimitive,
         error_kind=ERR_NEVER,
         format_str='{dest} = !{args[0]}',
         emit=simple_emit('{dest} = !{args[0]};'),
         priority=1)

method_op('__getitem__',
          arg_types=[object_rprimitive, object_rprimitive],
          result_type=object_rprimitive,
          error_kind=ERR_MAGIC,
          emit=call_emit('PyObject_GetItem'),
          priority=0)

method_op('__setitem__',
          arg_types=[object_rprimitive, object_rprimitive, object_rprimitive],
          result_type=bool_rprimitive,
          error_kind=ERR_FALSE,
          emit=call_negative_bool_emit('PyObject_SetItem'),
          priority=0)

method_op('__delitem__',
          arg_types=[object_rprimitive, object_rprimitive],
          result_type=bool_rprimitive,
          error_kind=ERR_FALSE,
          emit=call_negative_bool_emit('PyObject_DelItem'),
          priority=0)

func_op(
    name='builtins.hash',
    arg_types=[object_rprimitive],
    result_type=int_rprimitive,
    error_kind=ERR_MAGIC,
    emit=call_emit('CPyObject_Hash'))

py_getattr_op = func_op(
    name='builtins.getattr',
    arg_types=[object_rprimitive, object_rprimitive],
    result_type=object_rprimitive,
    error_kind=ERR_MAGIC,
    emit=call_emit('PyObject_GetAttr')
)

func_op(
    name='builtins.getattr',
    arg_types=[object_rprimitive, object_rprimitive, object_rprimitive],
    result_type=object_rprimitive,
    error_kind=ERR_MAGIC,
    emit=call_emit('CPyObject_GetAttr3')
)

py_setattr_op = func_op(
    name='builtins.setattr',
    arg_types=[object_rprimitive, object_rprimitive, object_rprimitive],
    result_type=bool_rprimitive,
    error_kind=ERR_FALSE,
    emit=call_negative_bool_emit('PyObject_SetAttr')
)

py_hasattr_op = func_op(
    name='builtins.hasattr',
    arg_types=[object_rprimitive, object_rprimitive],
    result_type=bool_rprimitive,
    error_kind=ERR_NEVER,
    emit=call_emit('PyObject_HasAttr')
)

py_calc_meta_op = custom_op(
    arg_types=[object_rprimitive, object_rprimitive],
    result_type=object_rprimitive,
    error_kind=ERR_MAGIC,
    format_str='{dest} = py_calc_metaclass({comma_args})',
    emit=simple_emit(
        '{dest} = (PyObject*) _PyType_CalculateMetaclass((PyTypeObject *){args[0]}, {args[1]});'),
    is_borrowed=True
)

py_delattr_op = func_op(
    name='builtins.delattr',
    arg_types=[object_rprimitive, object_rprimitive],
    result_type=bool_rprimitive,
    error_kind=ERR_FALSE,
    emit=call_negative_bool_emit('PyObject_DelAttr')
)

py_call_op = custom_op(
    arg_types=[object_rprimitive],
    result_type=object_rprimitive,
    is_var_arg=True,
    error_kind=ERR_MAGIC,
    format_str='{dest} = py_call({comma_args})',
    emit=simple_emit('{dest} = PyObject_CallFunctionObjArgs({comma_args}, NULL);'))

py_call_with_kwargs_op = custom_op(
    arg_types=[object_rprimitive],
    result_type=object_rprimitive,
    is_var_arg=True,
    error_kind=ERR_MAGIC,
    format_str='{dest} = py_call_with_kwargs({args[0]}, {args[1]}, {args[2]})',
    emit=call_emit('PyObject_Call'))


py_method_call_op = custom_op(
    arg_types=[object_rprimitive],
    result_type=object_rprimitive,
    is_var_arg=True,
    error_kind=ERR_MAGIC,
    format_str='{dest} = py_method_call({comma_args})',
    emit=simple_emit('{dest} = PyObject_CallMethodObjArgs({comma_args}, NULL);'))


import_op = custom_op(
    name='import',
    arg_types=[str_rprimitive],
    result_type=object_rprimitive,
    error_kind=ERR_MAGIC,
    emit=call_emit('PyImport_Import'))


get_module_dict_op = custom_op(
    name='get_module_dict',
    arg_types=[],
    result_type=dict_rprimitive,
    error_kind=ERR_NEVER,
    emit=call_emit('PyImport_GetModuleDict'),
    is_borrowed=True)


func_op('builtins.isinstance',
        arg_types=[object_rprimitive, object_rprimitive],
        result_type=bool_rprimitive,
        error_kind=ERR_MAGIC,
        emit=call_negative_magic_emit('PyObject_IsInstance'))

# Faster isinstance() that only works with native classes and doesn't perform type checking
# of the type argument.
fast_isinstance_op = func_op(
    'builtins.isinstance',
    arg_types=[object_rprimitive, object_rprimitive],
    result_type=bool_rprimitive,
    error_kind=ERR_NEVER,
    emit=simple_emit('{dest} = PyObject_TypeCheck({args[0]}, (PyTypeObject *){args[1]});'),
    priority=0)

type_is_op = custom_op(
    name='type_is',
    arg_types=[object_rprimitive, object_rprimitive],
    result_type=bool_rprimitive,
    error_kind=ERR_NEVER,
    emit=simple_emit('{dest} = Py_TYPE({args[0]}) == (PyTypeObject *){args[1]};'))

bool_op = func_op(
    'builtins.bool',
    arg_types=[object_rprimitive],
    result_type=bool_rprimitive,
    error_kind=ERR_MAGIC,
    emit=call_negative_magic_emit('PyObject_IsTrue'))

new_slice_op = func_op(
    'builtins.slice',
    arg_types=[object_rprimitive, object_rprimitive, object_rprimitive],
    result_type=object_rprimitive,
    error_kind=ERR_MAGIC,
    emit=call_emit('PySlice_New'))

type_op = func_op(
    'builtins.type',
    arg_types=[object_rprimitive],
    result_type=object_rprimitive,
    error_kind=ERR_NEVER,
    emit=call_emit('PyObject_Type'))

type_object_op = name_ref_op(
    'builtins.type',
    result_type=object_rprimitive,
    error_kind=ERR_NEVER,
    emit=name_emit('(PyObject*) &PyType_Type'),
    is_borrowed=True)

func_op(name='builtins.len',
        arg_types=[object_rprimitive],
        result_type=int_rprimitive,
        error_kind=ERR_NEVER,
        emit=call_emit('CPyObject_Size'),
        priority=0)

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
