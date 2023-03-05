"""Constant folding of IR values.

For example, 3 + 5 can be constant folded into 8.

This is mostly like mypy.constant_fold, but we can bind some additional
NameExpr and MemberExpr references here, since we have more knowledge
about which definitions can be trusted -- we constant fold only references
to other compiled modules in the same compilation unit.
"""

from __future__ import annotations

from typing import Union
from typing_extensions import Final

from mypy.constant_fold import constant_fold_binary_op, constant_fold_unary_int_op
from mypy.nodes import (
    ComplexExpr,
    Expression,
    FloatExpr,
    IntExpr,
    MemberExpr,
    NameExpr,
    OpExpr,
    StrExpr,
    UnaryExpr,
    Var,
)
from mypyc.irbuild.builder import IRBuilder

# All possible result types of constant folding
ConstantValue = Union[int, float, complex, str]
CONST_TYPES: Final = (int, float, complex, str)


def constant_fold_expr(builder: IRBuilder, expr: Expression) -> ConstantValue | None:
    """Return the constant value of an expression for supported operations.

    Return None otherwise.
    """
    if isinstance(expr, IntExpr):
        return expr.value
    if isinstance(expr, FloatExpr):
        return expr.value
    if isinstance(expr, StrExpr):
        return expr.value
    if isinstance(expr, ComplexExpr):
        return expr.value
    elif isinstance(expr, NameExpr):
        node = expr.node
        if isinstance(node, Var) and node.is_final:
            value = node.final_value
            if isinstance(value, (CONST_TYPES)):
                return value
    elif isinstance(expr, MemberExpr):
        final = builder.get_final_ref(expr)
        if final is not None:
            fn, final_var, native = final
            if final_var.is_final:
                value = final_var.final_value
                if isinstance(value, (CONST_TYPES)):
                    return value
    elif isinstance(expr, OpExpr):
        left = constant_fold_expr(builder, expr.left)
        right = constant_fold_expr(builder, expr.right)
        value = constant_fold_binary_op(expr.op, left, right)
        if value is not None:
            return value
    elif isinstance(expr, UnaryExpr):
        value = constant_fold_expr(builder, expr.expr)
        if isinstance(value, int):
            return constant_fold_unary_int_op(expr.op, value)
    return None
