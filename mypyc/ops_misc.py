"""Miscellaneous primitive ops."""

from typing import List

from mypyc.ops import (
    EmitterInterface, PrimitiveOp, none_rprimitive, bool_rprimitive, object_rprimitive, ERR_NEVER,
    ERR_MAGIC
)
from mypyc.ops_primitive import name_ref_op, simple_emit, binary_op


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
              emit=simple_emit('{dest} = PyObject_RichCompare({args[0]}, {args[1]}, %s);' % opid))
