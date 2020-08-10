"""Fallback primitive operations that operate on 'object' operands.

These just call the relevant Python C API function or a thin wrapper
around an API function. Most of these also have faster, specialized
ops that operate on some more specific types.

Many of these ops are given a low priority (0) so that specialized ops
will take precedence. If your specialized op doesn't seem to be used,
check that the priorities are configured properly.
"""

from mypyc.ir.ops import ERR_NEVER, ERR_MAGIC, ERR_NEG_INT
from mypyc.ir.rtypes import object_rprimitive, int_rprimitive, bool_rprimitive, c_int_rprimitive
from mypyc.primitives.registry import (
    binary_op, unary_op, custom_op, call_emit, simple_emit,
    call_negative_magic_emit, negative_int_emit,
    c_binary_op, c_unary_op, c_method_op, c_function_op, c_custom_op
)


# Binary operations

for op, opid in [('==', 2),   # PY_EQ
                 ('!=', 3),   # PY_NE
                 ('<',  0),   # PY_LT
                 ('<=', 1),   # PY_LE
                 ('>',  4),   # PY_GT
                 ('>=', 5)]:  # PY_GE
    # The result type is 'object' since that's what PyObject_RichCompare returns.
    c_binary_op(name=op,
                arg_types=[object_rprimitive, object_rprimitive],
                return_type=object_rprimitive,
                c_function_name='PyObject_RichCompare',
                error_kind=ERR_MAGIC,
                extra_int_constant=(opid, c_int_rprimitive),
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
    c_binary_op(name=op,
                arg_types=[object_rprimitive, object_rprimitive],
                return_type=object_rprimitive,
                c_function_name=funcname,
                error_kind=ERR_MAGIC,
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
    c_binary_op(name=op,
                arg_types=[object_rprimitive, object_rprimitive],
                return_type=object_rprimitive,
                c_function_name=funcname,
                error_kind=ERR_MAGIC,
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
    c_unary_op(name=op,
               arg_type=object_rprimitive,
               return_type=object_rprimitive,
               c_function_name=funcname,
               error_kind=ERR_MAGIC,
               priority=0)

unary_op(op='not',
         arg_type=object_rprimitive,
         result_type=bool_rprimitive,
         error_kind=ERR_MAGIC,
         format_str='{dest} = not {args[0]}',
         emit=call_negative_magic_emit('PyObject_Not'),
         priority=0)


# obj1[obj2]
c_method_op(name='__getitem__',
            arg_types=[object_rprimitive, object_rprimitive],
            return_type=object_rprimitive,
            c_function_name='PyObject_GetItem',
            error_kind=ERR_MAGIC,
            priority=0)

# obj1[obj2] = obj3
c_method_op(
    name='__setitem__',
    arg_types=[object_rprimitive, object_rprimitive, object_rprimitive],
    return_type=c_int_rprimitive,
    c_function_name='PyObject_SetItem',
    error_kind=ERR_NEG_INT,
    priority=0)

# del obj1[obj2]
c_method_op(
    name='__delitem__',
    arg_types=[object_rprimitive, object_rprimitive],
    return_type=c_int_rprimitive,
    c_function_name='PyObject_DelItem',
    error_kind=ERR_NEG_INT,
    priority=0)

# hash(obj)
c_function_op(
    name='builtins.hash',
    arg_types=[object_rprimitive],
    return_type=int_rprimitive,
    c_function_name='CPyObject_Hash',
    error_kind=ERR_MAGIC)

# getattr(obj, attr)
py_getattr_op = c_function_op(
    name='builtins.getattr',
    arg_types=[object_rprimitive, object_rprimitive],
    return_type=object_rprimitive,
    c_function_name='CPyObject_GetAttr',
    error_kind=ERR_MAGIC)

# getattr(obj, attr, default)
c_function_op(
    name='builtins.getattr',
    arg_types=[object_rprimitive, object_rprimitive, object_rprimitive],
    return_type=object_rprimitive,
    c_function_name='CPyObject_GetAttr3',
    error_kind=ERR_MAGIC)

# setattr(obj, attr, value)
py_setattr_op = c_function_op(
    name='builtins.setattr',
    arg_types=[object_rprimitive, object_rprimitive, object_rprimitive],
    return_type=c_int_rprimitive,
    c_function_name='PyObject_SetAttr',
    error_kind=ERR_NEG_INT)

# hasattr(obj, attr)
py_hasattr_op = c_function_op(
    name='builtins.hasattr',
    arg_types=[object_rprimitive, object_rprimitive],
    return_type=bool_rprimitive,
    c_function_name='PyObject_HasAttr',
    error_kind=ERR_NEVER)

# del obj.attr
py_delattr_op = c_function_op(
    name='builtins.delattr',
    arg_types=[object_rprimitive, object_rprimitive],
    return_type=c_int_rprimitive,
    c_function_name='PyObject_DelAttr',
    error_kind=ERR_NEG_INT)

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
    emit=simple_emit('{dest} = CPyObject_CallMethodObjArgs({comma_args}, NULL);'))

# len(obj)
generic_len_op = c_custom_op(
    arg_types=[object_rprimitive],
    return_type=int_rprimitive,
    c_function_name='CPyObject_Size',
    error_kind=ERR_NEVER)

# iter(obj)
iter_op = c_function_op(name='builtins.iter',
                        arg_types=[object_rprimitive],
                        return_type=object_rprimitive,
                        c_function_name='PyObject_GetIter',
                        error_kind=ERR_MAGIC)
# next(iterator)
#
# Although the error_kind is set to be ERR_NEVER, this can actually
# return NULL, and thus it must be checked using Branch.IS_ERROR.
next_op = c_custom_op(arg_types=[object_rprimitive],
                      return_type=object_rprimitive,
                      c_function_name='PyIter_Next',
                      error_kind=ERR_NEVER)
# next(iterator)
#
# Do a next, don't swallow StopIteration, but also don't propagate an
# error. (N.B: This can still return NULL without an error to
# represent an implicit StopIteration, but if StopIteration is
# *explicitly* raised this will not swallow it.)
# Can return NULL: see next_op.
next_raw_op = c_custom_op(arg_types=[object_rprimitive],
                          return_type=object_rprimitive,
                          c_function_name='CPyIter_Next',
                          error_kind=ERR_NEVER)
