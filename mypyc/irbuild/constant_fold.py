"""Constant folding of IR values.

For example, 3 + 5 can be constant folded into 8.
"""

from typing import Optional, Union

from mypy.nodes import Expression, IntExpr, OpExpr, UnaryExpr, NameExpr, MemberExpr, Var
from mypyc.irbuild.builder import IRBuilder


ConstantValue = Union[int]


def constant_fold_expr(builder: IRBuilder, expr: Expression) -> Optional[ConstantValue]:
    if isinstance(expr, IntExpr):
        return expr.value
    elif isinstance(expr, NameExpr):
        node = expr.node
        if isinstance(node, Var) and node.is_final:
            value = node.final_value
            if isinstance(value, int):
                return value
    elif isinstance(expr, MemberExpr):
        final = builder.get_final_ref(expr)
        if final is not None:
            fn, final_var, native = final
            if final_var.is_final:
                value = final_var.final_value
                if isinstance(value, int):
                    return value
    elif isinstance(expr, OpExpr):
        left = constant_fold_expr(builder, expr.left)
        right = constant_fold_expr(builder, expr.right)
        if isinstance(left, int) and isinstance(right, int):
            return constant_fold_binary_int_op(expr.op, left, right)
    elif isinstance(expr, UnaryExpr):
        value = constant_fold_expr(builder, expr.expr)
        if isinstance(value, int):
            return constant_fold_unary_int_op(expr.op, value)
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


def constant_fold_unary_int_op(op: str, value: int) -> Optional[int]:
    if op == '-':
        return -value
    elif op == '~':
        return ~value
    elif op == '+':
        return value
    return None
