"""Miscellaneous primitive ops."""

from typing import List

from mypyc.ops import (
    EmitterInterface, PrimitiveOp, none_rprimitive, bool_rprimitive, object_rprimitive, ERR_NEVER,
    ERR_MAGIC, ERR_FALSE
)
from mypyc.ops_primitive import name_ref_op, simple_emit, binary_op, unary_op, func_op, method_op


def emit_none(emitter: EmitterInterface, args: List[str], dest: str) -> None:
    emitter.emit_lines('{} = Py_None;'.format(dest),
                       'Py_INCREF({});'.format(dest))


none_op = name_ref_op('builtins.None',
                      result_type=none_rprimitive,
                      error_kind=ERR_NEVER,
                      emit=emit_none)

true_op = name_ref_op('builtins.True',
                      result_type=bool_rprimitive,
                      error_kind=ERR_NEVER,
                      emit=simple_emit('{dest} = 1;'))

false_op = name_ref_op('builtins.False',
                       result_type=bool_rprimitive,
                       error_kind=ERR_NEVER,
                       emit=simple_emit('{dest} = 0;'))

iter_op = func_op(name='builtins.iter',
                  arg_types=[object_rprimitive],
                  result_type=object_rprimitive,
                  error_kind=ERR_MAGIC,
                  emit=simple_emit('{dest} = PyObject_GetIter({args[0]});'))

# Although the error_kind is set to be ERR_NEVER, this can actually return NULL, and thus it must
# be checked using Branch.IS_ERROR.
next_op = func_op(name='builtins.next',
                  arg_types=[object_rprimitive],
                  result_type=object_rprimitive,
                  error_kind=ERR_NEVER,
                  emit=simple_emit('{dest} = PyIter_Next({args[0]});'))

no_err_occurred_op = func_op(name='no_err_occurred',
                             arg_types=[],
                             result_type=bool_rprimitive,
                             error_kind=ERR_FALSE,
                             emit=simple_emit('{dest} = (PyErr_Occurred() == NULL);'))

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

binary_op(op='**',
          arg_types=[object_rprimitive, object_rprimitive],
          result_type=object_rprimitive,
          error_kind=ERR_MAGIC,
          emit=simple_emit('{dest} = PyNumber_Power({args[0]}, {args[1]}, Py_None);'),
          priority=0)


def emit_in(emitter: EmitterInterface, args: List[str], dest: str) -> None:
    temp = emitter.temp_name()
    emitter.emit_lines('int %s = PySequence_Contains(%s, %s);' % (temp, args[1], args[0]),
                       'if (%s < 0)' % temp,
                       '    %s = %s;' % (dest, bool_rprimitive.c_error_value()),
                       'else',
                       '    %s = %s;' % (dest, temp))


binary_op('in',
          arg_types=[object_rprimitive, object_rprimitive],
          result_type=bool_rprimitive,
          error_kind=ERR_MAGIC,
          emit=emit_in,
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


def emit_isinstance(emitter: EmitterInterface, args: List[str], dest: str) -> None:
    temp = emitter.temp_name()
    emitter.emit_lines('int %s = PyObject_IsInstance(%s, %s);' % (temp, args[0], args[1]),
                       'if (%s < 0)' % temp,
                       '    %s = %s;' % (dest, bool_rprimitive.c_error_value()),
                       'else',
                       '    %s = %s;' % (dest, temp))


func_op('builtins.isinstance',
        arg_types=[object_rprimitive, object_rprimitive],
        result_type=bool_rprimitive,
        error_kind=ERR_MAGIC,
        emit=emit_isinstance)
