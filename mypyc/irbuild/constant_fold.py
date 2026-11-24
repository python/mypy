"""Constant folding of IR values.

For example, 3 + 5 can be constant folded into 8.

This is mostly like mypy.constant_fold, but we can bind some additional
NameExpr and MemberExpr references here, since we have more knowledge
about which definitions can be trusted -- we constant fold only references
to other compiled modules in the same compilation unit.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from mypy.constant_fold import constant_fold_binary_op, constant_fold_unary_op
from mypy.nodes import (
    BytesExpr,
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
from mypyc.ir.rtypes import (
    RPrimitive,
    is_fixed_width_rtype,
    wrap_native_int,
    wrap_unsigned_native_int,
)
from mypyc.irbuild.util import bytes_from_str

if TYPE_CHECKING:
    from mypyc.irbuild.builder import IRBuilder

# All possible result types of constant folding
ConstantValue = int | float | complex | str | bytes
CONST_TYPES: Final = (int, float, complex, str, bytes)


def constant_fold_expr(builder: IRBuilder, expr: Expression) -> ConstantValue | None:
    """Return the constant value of an expression for supported operations.

    Return None otherwise.
    """
    value = constant_fold_expr_inner(builder, expr)
    if isinstance(value, int) and not isinstance(value, bool) and not isinstance(expr, IntExpr):
        # Evaluate each operation using native int semantics if needed, since
        # unsigned native ints wrap around on overflow (e.g. -X if X is a u64).
        # Bools are skipped, since the helper returns a plain int when compiled.
        value = wrap_unsigned_native_int(builder.node_type(expr), value)
    return value


def constant_fold_expr_inner(builder: IRBuilder, expr: Expression) -> ConstantValue | None:
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
            if expr.op in ("<<", ">>") and isinstance(left, int) and isinstance(right, int):
                rtype = builder.node_type(expr)
                if is_fixed_width_rtype(rtype):
                    return constant_fold_native_int_shift(rtype, expr.op, left, right)
            return constant_fold_binary_op_extended(expr.op, left, right)
    elif isinstance(expr, UnaryExpr):
        value = constant_fold_expr(builder, expr.expr)
        if value is not None and not isinstance(value, bytes):
            return constant_fold_unary_op(expr.op, value)
    return None


def constant_fold_native_int_shift(rtype: RPrimitive, op: str, left: int, right: int) -> int:
    """Fold a shift of a fixed-width native int (see IntOp for the semantics).

    A count that is negative or at least the bit width gives 0, or -1 for a right shift
    of a negative value. A left shift wraps around, also for signed types.
    """
    if not 0 <= right < 8 * rtype.size:
        return -1 if op == ">>" and left < 0 else 0
    if op == ">>":
        return left >> right
    return wrap_native_int(rtype, left << right)


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
