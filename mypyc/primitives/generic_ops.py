"""Fallback primitive operations that operate on 'object' operands.

These just call the relevant Python C API function or a thin wrapper
around an API function. Most of these also have faster, specialized
ops that operate on some more specific types.

Many of these ops are given a low priority (0) so that specialized ops
will take precedence. If your specialized op doesn't seem to be used,
check that the priorities are configured properly.
"""

from mypyc.ir.ops import ERR_NEVER, ERR_MAGIC, ERR_FALSE
from mypyc.ir.rtypes import object_rprimitive, int_rprimitive, bool_rprimitive
from mypyc.primitives.registry import (
    binary_op, unary_op, func_op, method_op, custom_op, call_emit, simple_emit,
    call_negative_bool_emit, call_negative_magic_emit, negative_int_emit
)


# Binary operations

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
              emit=call_emit(funcname),
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


# Unary operations

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


# obj1[obj2]
method_op('__getitem__',
          arg_types=[object_rprimitive, object_rprimitive],
          result_type=object_rprimitive,
          error_kind=ERR_MAGIC,
          emit=call_emit('PyObject_GetItem'),
          priority=0)

# obj1[obj2] = obj3
method_op('__setitem__',
          arg_types=[object_rprimitive, object_rprimitive, object_rprimitive],
          result_type=bool_rprimitive,
          error_kind=ERR_FALSE,
          emit=call_negative_bool_emit('PyObject_SetItem'),
          priority=0)

# del obj1[obj2]
method_op('__delitem__',
          arg_types=[object_rprimitive, object_rprimitive],
          result_type=bool_rprimitive,
          error_kind=ERR_FALSE,
          emit=call_negative_bool_emit('PyObject_DelItem'),
          priority=0)

# hash(obj)
func_op(
    name='builtins.hash',
    arg_types=[object_rprimitive],
    result_type=int_rprimitive,
    error_kind=ERR_MAGIC,
    emit=call_emit('CPyObject_Hash'))

# getattr(obj, attr)
py_getattr_op = func_op(
    name='builtins.getattr',
    arg_types=[object_rprimitive, object_rprimitive],
    result_type=object_rprimitive,
    error_kind=ERR_MAGIC,
    emit=call_emit('PyObject_GetAttr')
)

# getattr(obj, attr, default)
func_op(
    name='builtins.getattr',
    arg_types=[object_rprimitive, object_rprimitive, object_rprimitive],
    result_type=object_rprimitive,
    error_kind=ERR_MAGIC,
    emit=call_emit('CPyObject_GetAttr3')
)

# setattr(obj, attr, value)
py_setattr_op = func_op(
    name='builtins.setattr',
    arg_types=[object_rprimitive, object_rprimitive, object_rprimitive],
    result_type=bool_rprimitive,
    error_kind=ERR_FALSE,
    emit=call_negative_bool_emit('PyObject_SetAttr')
)

# hasattr(obj, attr)
py_hasattr_op = func_op(
    name='builtins.hasattr',
    arg_types=[object_rprimitive, object_rprimitive],
    result_type=bool_rprimitive,
    error_kind=ERR_NEVER,
    emit=call_emit('PyObject_HasAttr')
)

# del obj.attr
py_delattr_op = func_op(
    name='builtins.delattr',
    arg_types=[object_rprimitive, object_rprimitive],
    result_type=bool_rprimitive,
    error_kind=ERR_FALSE,
    emit=call_negative_bool_emit('PyObject_DelAttr')
)

# Call callable object with N positional arguments: func(arg1, ..., argN)
# Arguments are (func, arg1, ..., argN).
py_call_op = custom_op(
    arg_types=[object_rprimitive],
    result_type=object_rprimitive,
    is_var_arg=True,
    error_kind=ERR_MAGIC,
    format_str='{dest} = py_call({comma_args})',
    emit=simple_emit('{dest} = PyObject_CallFunctionObjArgs({comma_args}, NULL);'))

# Call callable object with positional + keyword args: func(*args, **kwargs)
# Arguments are (func, *args tuple, **kwargs dict).
py_call_with_kwargs_op = custom_op(
    arg_types=[object_rprimitive, object_rprimitive, object_rprimitive],
    result_type=object_rprimitive,
    error_kind=ERR_MAGIC,
    format_str='{dest} = py_call_with_kwargs({args[0]}, {args[1]}, {args[2]})',
    emit=call_emit('PyObject_Call'))

# Call method with positional arguments: obj.method(arg1, ...)
# Arguments are (object, attribute name, arg1, ...).
py_method_call_op = custom_op(
    arg_types=[object_rprimitive],
    result_type=object_rprimitive,
    is_var_arg=True,
    error_kind=ERR_MAGIC,
    format_str='{dest} = py_method_call({comma_args})',
    emit=simple_emit('{dest} = PyObject_CallMethodObjArgs({comma_args}, NULL);'))

# len(obj)
func_op(name='builtins.len',
        arg_types=[object_rprimitive],
        result_type=int_rprimitive,
        error_kind=ERR_NEVER,
        emit=call_emit('CPyObject_Size'),
        priority=0)

# iter(obj)
iter_op = func_op(name='builtins.iter',
                  arg_types=[object_rprimitive],
                  result_type=object_rprimitive,
                  error_kind=ERR_MAGIC,
                  emit=call_emit('PyObject_GetIter'))

# next(iterator)
#
# Although the error_kind is set to be ERR_NEVER, this can actually
# return NULL, and thus it must be checked using Branch.IS_ERROR.
next_op = custom_op(name='next',
                    arg_types=[object_rprimitive],
                    result_type=object_rprimitive,
                    error_kind=ERR_NEVER,
                    emit=call_emit('PyIter_Next'))

# next(iterator)
#
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
