"""Constant folding of IR values.

For example, 3 + 5 can be constant folded into 8.

This is mostly like mypy.constant_fold, but we can bind some additional
NameExpr and MemberExpr references here, since we have more knowledge
about which definitions can be trusted -- we constant fold only references
to other compiled modules in the same compilation unit.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, Union, overload

from mypy.checkexpr import try_getting_literal
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
from mypy.types import LiteralType, TupleType, get_proper_type
from mypyc.irbuild.builder import IRBuilder
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
    # we can also constant fold some common methods of builtin types
    elif isinstance(expr, CallExpr) and isinstance(callee := expr.callee, MemberExpr):
        folded_callee = constant_fold_expr(builder, callee.expr)

        # builtins.str methods
        if isinstance(folded_callee, str):
            # str.join
            if callee.name == "join" and len(args := expr.args) == 1:
                arg = args[0]
                if isinstance(arg, (ListExpr, TupleExpr)):
                    folded_items = constant_fold_container_expr(builder, arg)
                    if folded_items is not None and all(
                        isinstance(item, str) for item in folded_items
                    ):
                        return folded_callee.join(folded_items)  # type: ignore [arg-type]
                if expr_type := builder.types.get(arg):
                    proper_type = get_proper_type(expr_type)
                    if isinstance(proper_type, TupleType):
                        values: list[str] = []
                        for item_type in map(try_getting_literal, proper_type.items):
                            if not (
                                isinstance(item_type, LiteralType)
                                and isinstance(item_type.value, str)
                            ):
                                return None
                            values.append(item_type.value)
                        return folded_callee.join(values)

        # builtins.bytes methods
        elif isinstance(folded_callee, bytes):
            # bytes.join
            if (
                callee.name == "join"
                and len(args := expr.args) == 1
                # TODO extend this to work with rtuples comprised of known literal values
                and isinstance(arg := args[0], (ListExpr, TupleExpr))
            ):
                folded_items = constant_fold_container_expr(builder, arg)
                if folded_items is not None and all(
                    isinstance(item, bytes) for item in folded_items
                ):
                    return folded_callee.join(folded_items)  # type: ignore [arg-type]
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


@overload
def constant_fold_container_expr(
    builder: IRBuilder, expr: ListExpr
) -> list[ConstantValue] | None: ...
@overload
def constant_fold_container_expr(
    builder: IRBuilder, expr: TupleExpr
) -> tuple[ConstantValue, ...] | None: ...
def constant_fold_container_expr(
    builder: IRBuilder, expr: ListExpr | TupleExpr
) -> list[ConstantValue] | tuple[ConstantValue, ...] | None:
    folded_items = [constant_fold_expr(builder, item_expr) for item_expr in expr.items]
    if None in folded_items:
        return None
    if isinstance(expr, ListExpr):
        return folded_items  # type: ignore [return-value]
    elif isinstance(expr, TupleExpr):
        return tuple(folded_items)  # type: ignore [arg-type]
    else:
        raise NotImplementedError(type(expr), expr)
