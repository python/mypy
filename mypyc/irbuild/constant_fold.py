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
    AssignmentStmt,
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
    check_native_int_range,
    is_fixed_width_rtype,
    wrap_native_int,
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
    if (
        isinstance(value, int)
        and not isinstance(value, bool)
        and isinstance(expr, (OpExpr, UnaryExpr))
    ):
        # Evaluate each operation using native int semantics if needed, since
        # native ints wrap around on overflow (e.g. -X if X is a u64).
        # References to finals aren't wrapped: a final defined in an interpreted
        # module can have an out-of-range value, which must be reported instead.
        # (In a compiled module, check_native_int_final ensures that the value
        # computed by mypy for a constant initializer is in range.)
        # Bools are skipped, since the helper returns a plain int when compiled.
        value = wrap_native_int(builder.node_type(expr), value)
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
            result = constant_fold_binary_op_extended(expr.op, left, right)
            if expr.op == "//" and isinstance(result, int):
                rtype = builder.node_type(expr)
                if is_fixed_width_rtype(rtype) and not check_native_int_range(rtype, result):
                    # Signed MIN // -1 raises OverflowError at runtime instead of wrapping
                    # around, so don't fold it
                    return None
            return result
    elif isinstance(expr, UnaryExpr):
        value = constant_fold_expr(builder, expr.expr)
        if value is not None and not isinstance(value, bytes):
            return constant_fold_unary_op(expr.op, value)
    return None


def check_native_int_final(builder: IRBuilder, stmt: AssignmentStmt) -> None:
    """Report an error if uses of a native int final could get the wrong value.

    Uses of a final with a value computed by mypy (final_value) get that value instead
    of reading the value stored by the definition. Mypy evaluates the initializer using
    int semantics, so its value can be wrong if a native int operation wraps around.
    For example, if ONE is an i8 final with value 1, "ONE << 7" is 128 for mypy but
    -128 in compiled code, and "(ONE << 7) >> 7" is 1 instead of -1. Require the value
    to be in range, and to match the value mypyc computes using native int semantics.

    The final itself doesn't need to have a native int type for this to happen, as in
    "X: Final = ONE << 7" (mypy infers int for a final with a constant value) or
    "X: Final[object] = ONE << 7". Use the type of the initializer in this case.
    """
    if not stmt.is_final_def or len(stmt.lvalues) != 1:
        return
    lvalue = stmt.lvalues[0]
    if not isinstance(lvalue, NameExpr) or not isinstance(lvalue.node, Var):
        return
    value = lvalue.node.final_value
    if not isinstance(value, int) or isinstance(value, bool):
        return
    rtype = builder.node_type(lvalue)
    if not is_fixed_width_rtype(rtype):
        rtype = builder.node_type(stmt.rvalue)
    if not is_fixed_width_rtype(rtype):
        return
    if not check_native_int_range(rtype, value):
        builder.error(f'Value {value} is out of range for "{rtype}"', stmt.line)
        return
    folded = constant_fold_expr(builder, stmt.rvalue)
    if not isinstance(folded, int):
        # mypy folds True and False, but mypyc doesn't (e.g. "True + 1")
        builder.error(f'Unsupported value for final "{lvalue.name}"', stmt.line)
    elif folded != value:
        builder.error(
            f'Unsupported value for final "{lvalue.name}" '
            f'(intermediate result overflows "{rtype}")',
            stmt.line,
        )


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
