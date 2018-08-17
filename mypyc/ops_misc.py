"""Miscellaneous primitive ops."""

from typing import List

from mypyc.ops import (
    EmitterInterface, PrimitiveOp,
    none_rprimitive, bool_rprimitive, object_rprimitive, tuple_rprimitive, str_rprimitive,
    ERR_NEVER, ERR_MAGIC, ERR_FALSE
)
from mypyc.ops_primitive import (
    name_ref_op, simple_emit, binary_op, unary_op, func_op, method_op, custom_op,
    negative_int_emit,
)


# N.B: none_op is special cased as borrowed by PrimitiveOp
none_op = name_ref_op('builtins.None',
                      result_type=none_rprimitive,
                      error_kind=ERR_NEVER,
                      emit=simple_emit('{dest} = Py_None;'))

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
                        emit=simple_emit('{dest} = Py_Ellipsis; Py_INCREF({dest});'))

iter_op = func_op(name='builtins.iter',
                  arg_types=[object_rprimitive],
                  result_type=object_rprimitive,
                  error_kind=ERR_MAGIC,
                  emit=simple_emit('{dest} = PyObject_GetIter({args[0]});'))

# Although the error_kind is set to be ERR_NEVER, this can actually return NULL, and thus it must
# be checked using Branch.IS_ERROR.
next_op = custom_op(name='next',
                    arg_types=[object_rprimitive],
                    result_type=object_rprimitive,
                    error_kind=ERR_NEVER,
                    emit=simple_emit('{dest} = PyIter_Next({args[0]});'))

method_new_op = custom_op(name='method_new',
                          arg_types=[object_rprimitive, object_rprimitive],
                          result_type=object_rprimitive,
                          error_kind=ERR_MAGIC,
                          emit=simple_emit('{dest} = PyMethod_New({args[0]}, {args[1]});'))


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
              emit=simple_emit('{dest} = %s({args[0]}, {args[1]});' % funcname),
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
             emit=simple_emit('{dest} = %s({args[0]});' % funcname),
             priority=0)

unary_op(op='not',
         arg_type=object_rprimitive,
         result_type=bool_rprimitive,
         error_kind=ERR_MAGIC,
         format_str='{dest} = not {args[0]}',
         emit=negative_int_emit('{dest} = PyObject_Not({args[0]});'),
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
          emit=simple_emit('{dest} = PyObject_GetItem({args[0]}, {args[1]});'),
          priority=0)

method_op('__setitem__',
          arg_types=[object_rprimitive, object_rprimitive, object_rprimitive],
          result_type=bool_rprimitive,
          error_kind=ERR_FALSE,
          emit=simple_emit('{dest} = PyObject_SetItem({args[0]}, {args[1]}, {args[2]}) >= 0;'),
          priority=0)

method_op('__delitem__',
          arg_types=[object_rprimitive, object_rprimitive],
          result_type=bool_rprimitive,
          error_kind=ERR_FALSE,
          emit=simple_emit('{dest} = PyObject_DelItem({args[0]}, {args[1]}) >= 0;'),
          priority=0)

py_getattr_op = func_op(
    name='builtins.getattr',
    arg_types=[object_rprimitive, object_rprimitive],
    result_type=object_rprimitive,
    error_kind=ERR_MAGIC,
    emit=simple_emit('{dest} = PyObject_GetAttr({args[0]}, {args[1]});')
)

py_setattr_op = func_op(
    name='builtins.setattr',
    arg_types=[object_rprimitive, object_rprimitive, object_rprimitive],
    result_type=bool_rprimitive,
    error_kind=ERR_FALSE,
    emit=simple_emit('{dest} = PyObject_SetAttr({args[0]}, {args[1]}, {args[2]}) >= 0;')
)

py_delattr_op = func_op(
    name='builtins.delattr',
    arg_types=[object_rprimitive, object_rprimitive],
    result_type=bool_rprimitive,
    error_kind=ERR_FALSE,
    emit=simple_emit('{dest} = PyObject_DelAttr({args[0]}, {args[1]}) >= 0;')
)

py_call_op = custom_op(
    arg_types=[object_rprimitive],
    result_type=object_rprimitive,
    is_var_arg=True,
    error_kind=ERR_MAGIC,
    format_str = '{dest} = py_call({comma_args})',
    emit=simple_emit('{dest} = PyObject_CallFunctionObjArgs({comma_args}, NULL);'))

py_call_with_kwargs_op = custom_op(
    arg_types=[object_rprimitive],
    result_type=object_rprimitive,
    is_var_arg=True,
    error_kind=ERR_MAGIC,
    format_str = '{dest} = py_call_with_kwargs({args[0]}, {args[1]}, {args[2]})',
    emit=simple_emit('{dest} = PyObject_Call({args[0]}, {args[1]}, {args[2]});'))


py_method_call_op = custom_op(
    arg_types=[object_rprimitive],
    result_type=object_rprimitive,
    is_var_arg=True,
    error_kind=ERR_MAGIC,
    format_str = '{dest} = py_method_call({comma_args})',
    emit=simple_emit('{dest} = PyObject_CallMethodObjArgs({comma_args}, NULL);'))


import_op = custom_op(
    name='import',
    arg_types=[str_rprimitive],
    result_type=object_rprimitive,
    error_kind=ERR_MAGIC,
    emit=simple_emit('{dest} = PyImport_Import({args[0]});'))


func_op('builtins.isinstance',
        arg_types=[object_rprimitive, object_rprimitive],
        result_type=bool_rprimitive,
        error_kind=ERR_MAGIC,
        emit=negative_int_emit('{dest} = PyObject_IsInstance({args[0]}, {args[1]});'))

# Faster isinstance() that only works with native classes and doesn't perform type checking
# of the type argument.
fast_isinstance_op = func_op(
    'builtins.isinstance',
    arg_types=[object_rprimitive, object_rprimitive],
    result_type=bool_rprimitive,
    error_kind=ERR_NEVER,
    emit=simple_emit('{dest} = PyObject_TypeCheck({args[0]}, (PyTypeObject *){args[1]});'),
    priority=0)

bool_op = func_op(
    'builtins.bool',
    arg_types=[object_rprimitive],
    result_type=bool_rprimitive,
    error_kind=ERR_MAGIC,
    emit=negative_int_emit('{dest} = PyObject_IsTrue({args[0]});'))

new_slice_op = func_op(
    'builtins.slice',
    arg_types=[object_rprimitive, object_rprimitive, object_rprimitive],
    result_type=object_rprimitive,
    error_kind=ERR_MAGIC,
    emit=simple_emit('{dest} = PySlice_New({args[0]}, {args[1]}, {args[2]});'))

type_op = func_op(
    'builtins.type',
    arg_types=[object_rprimitive],
    result_type=object_rprimitive,
    error_kind=ERR_NEVER,
    emit=simple_emit('{dest} = PyObject_Type({args[0]});'))

pytype_from_template_op = custom_op(
    arg_types=[object_rprimitive, object_rprimitive, str_rprimitive],
    result_type=object_rprimitive,
    error_kind=ERR_MAGIC,
    format_str='{dest} = pytype_from_template({comma_args})',
    emit=simple_emit(
        '{dest} = CPyType_FromTemplate((PyTypeObject *){args[0]}, {args[1]}, {args[2]});'))
