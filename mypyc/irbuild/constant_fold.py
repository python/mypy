"""Constant folding of IR values.

For example, 3 + 5 can be constant folded into 8.

This is mostly like mypy.constant_fold, but we can bind some additional
NameExpr and MemberExpr references here, since we have more knowledge
about which definitions can be trusted -- we constant fold only references
to other compiled modules in the same compilation unit.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Final, Union

from mypy.constant_fold import constant_fold_binary_op, constant_fold_unary_op
from mypy.nodes import (
    BytesExpr,
    ComplexExpr,
    Expression,
    FloatExpr,
    IndexExpr,
    IntExpr,
    MemberExpr,
    NameExpr,
    OpExpr,
    SliceExpr,
    StrExpr,
    UnaryExpr,
    Var,
)
from mypyc.irbuild.util import bytes_from_str

if TYPE_CHECKING:
    from mypyc.irbuild.builder import IRBuilder

# All possible result types of constant folding
ConstantValue = Union[int, float, complex, str, bytes]
CONST_TYPES: Final = (int, float, complex, str, bytes)


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
    if isinstance(expr, BytesExpr):
        return bytes_from_str(expr.value)
    if isinstance(expr, ComplexExpr):
        return expr.value
    elif isinstance(expr, NameExpr):
        node = expr.node
        if isinstance(node, Var) and node.is_final:
            final_value = node.final_value
            if isinstance(final_value, (CONST_TYPES)):
                return final_value
    elif isinstance(expr, MemberExpr):
        final = builder.get_final_ref(expr)
        if final is not None:
            fn, final_var, native = final
            if final_var.is_final:
                final_value = final_var.final_value
                if isinstance(final_value, (CONST_TYPES)):
                    return final_value
    elif isinstance(expr, OpExpr):
        left = constant_fold_expr(builder, expr.left)
        right = constant_fold_expr(builder, expr.right)
        if left is not None and right is not None:
            return constant_fold_binary_op_extended(expr.op, left, right)
    elif isinstance(expr, UnaryExpr):
        value = constant_fold_expr(builder, expr.expr)
        if value is not None and not isinstance(value, bytes):
            return constant_fold_unary_op(expr.op, value)
    elif isinstance(expr, IndexExpr):
        base = constant_fold_expr(builder, expr.base)
        if base is not None:
            index_expr = expr.index
            if isinstance(index_expr, SliceExpr):
                if index_expr.begin_index is None:
                    begin_index = None
                else:
                    begin_index = constant_fold_expr(builder, index_expr.begin_index)
                    if begin_index is None:
                        return None
                if index_expr.end_index is None:
                    end_index = None
                else:
                    end_index = constant_fold_expr(builder, index_expr.end_index)
                    if end_index is None:
                        return None
                if index_expr.stride is None:
                    stride = None
                else:
                    stride = constant_fold_expr(builder, index_expr.stride)
                    if stride is None:
                        return None
                try:
                    return base[begin_index:end_index:stride]  # type: ignore [index, misc]
                except Exception:
                    return None

            index = constant_fold_expr(builder, index_expr)
            if index is not None:
                try:
                    return base[index]  # type: ignore [index]
                except Exception:
                    return None
    return None


def constant_fold_binary_op_extended(
    op: str, left: ConstantValue, right: ConstantValue
) -> ConstantValue | None:
    """Like mypy's constant_fold_binary_op(), but includes bytes support.

    mypy cannot use constant folded bytes easily so it's simpler to only support them in mypyc.
    """
    if not isinstance(left, bytes) and not isinstance(right, bytes):
        return constant_fold_binary_op(op, left, right)

    if op == "+" and isinstance(left, bytes) and isinstance(right, bytes):
        return left + right
    elif op == "*" and isinstance(left, bytes) and isinstance(right, int):
        return left * right
    elif op == "*" and isinstance(left, int) and isinstance(right, bytes):
        return left * right

    return None


def try_constant_fold(builder: IRBuilder, expr: Expression) -> Value | None:
    """Return the constant value of an expression if possible.

    Return None otherwise.
    """
    value = constant_fold_expr(builder, expr)
    if value is not None:
        return builder.load_literal_value(value)
    return None


def folding_candidate(
    transform: Callable[[IRBuilder, Expression], Value | None],
) -> Callable[[IRBuilder, Expression], Value | None]:
    """Mark a transform function as a candidate for constant folding.

    Candidate functions will attempt to short-circuit the transformation
    by constant folding the expression and will only proceed to transform
    the expression if folding is not possible.
    """
    def constant_fold_wrap(builder: IRBuilder, expr: Expression) -> Value | None:
        folded = try_constant_fold(builder, expr)
        return folded if folded is not None else transform(builder, expr)
    return constant_fold_wrap
