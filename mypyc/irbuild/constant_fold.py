"""Constant folding of IR values.

For example, 3 + 5 can be constant folded into 8.

This is mostly like mypy.constant_fold, but we can bind some additional
NameExpr and MemberExpr references here, since we have more knowledge
about which definitions can be trusted -- we constant fold only references
to other compiled modules in the same compilation unit.
"""

from __future__ import annotations

from typing import Final, Union

from mypy.constant_fold import constant_fold_binary_op, constant_fold_unary_op
from mypy.nodes import (
    BytesExpr,
    CallExpr,
    ComplexExpr,
    Expression,
    FloatExpr,
    IntExpr,
    ListExpr,
    MemberExpr,
    NameExpr,
    OpExpr,
    StrExpr,
    TupleExpr,
    UnaryExpr,
    Var,
)
from mypyc.irbuild.builder import IRBuilder
from mypyc.irbuild.util import bytes_from_str

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
    # we can also constant fold some common methods of builtin types
    elif isinstance(expr, CallExpr) and isinstance(callee := expr.callee, MemberExpr):
        folded_callee = constant_fold_expr(builder, callee.expr)

        # builtins.str methods
        if isinstance(folded_callee, str):
            # str.join
            if (
                callee.name == "join"
                and len(args := expr.args) == 1
                # TODO extend this to work with rtuples comprised of known literal values
                and isinstance(arg := args[0], (ListExpr, TupleExpr))
            ):
                folded_strings = []
                for item in arg.items:
                    val = constant_fold_expr(builder, item)
                    if not isinstance(val, str):
                        return None
                    folded_strings.append(val)
                return folded_callee.join(folded_strings)

        # builtins.bytes methods
        elif isinstance(folded_callee, bytes):
            # str.join
            if (
                callee.name == "join"
                and len(args := expr.args) == 1
                # TODO extend this to work with rtuples comprised of known literal values
                and isinstance(arg := args[0], (ListExpr, TupleExpr))
            ):
                folded_bytes = []
                for item in arg.items:
                    val = constant_fold_expr(builder, item)
                    if not isinstance(val, bytes):
                        return None
                    folded_bytes.append(val)
                return folded_callee.join(folded_bytes)
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
