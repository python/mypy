"""Constant folding of IR values.

For example, 3 + 5 can be constant folded into 8.
"""

from typing import Optional

from mypyc.common import MAX_LITERAL_SHORT_INT, MIN_LITERAL_SHORT_INT
from mypyc.ir.ops import Value, Integer
from mypyc.ir.rtypes import is_short_int_rprimitive


def constant_fold_binary_op(op: str, left: Value, right: Value) -> Optional[Value]:
    if (
        isinstance(left, Integer)
        and isinstance(right, Integer)
        and is_short_int_rprimitive(left.type)
        and is_short_int_rprimitive(right.type)
    ):
        value = constant_fold_binary_int_op(op, left.value // 2, right.value // 2)
        # TODO: Also constant fold operations that produce long integers
        if value is not None and MIN_LITERAL_SHORT_INT <= value <= MAX_LITERAL_SHORT_INT:
            return Integer(value, line=left.line)
    return None


def constant_fold_binary_int_op(op: str, left: int, right: int) -> Optional[int]:
    if op == '+':
        return left + right
    if op == '-':
        return left - right
    elif op == '*':
        return left * right
    elif op == '//':
        if right != 0:
            return left // right
    elif op == '%':
        if right != 0:
            return left % right
    elif op == '&':
        return left & right
    elif op == '|':
        return left | right
    elif op == '^':
        return left ^ right
    elif op == '<<':
        if right >= 0:
            return left << right
    elif op == '>>':
        if right >= 0:
            return left >> right
    elif op == '**':
        if right >= 0:
            return left ** right
    return None


def constant_fold_unary_op(op: str, value: Value) -> Optional[Value]:
    if isinstance(value, Integer) and is_short_int_rprimitive(value.type):
        if op == '-':
            return Integer(-value.value // 2, line=value.line)
        elif op == '~':
            return Integer(~value.value // 2, line=value.line)
        elif op == '+':
            return value
    return None
