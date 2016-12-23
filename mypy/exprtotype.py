"""Translate an Expression to a Type value."""

from mypy.nodes import (
    Expression, NameExpr, MemberExpr, IndexExpr, TupleExpr,
    ListExpr, StrExpr, BytesExpr, UnicodeExpr, EllipsisExpr
)
from mypy.parsetype import parse_str_as_type, TypeParseError
from mypy.types import Type, UnboundType, TypeList, EllipsisType


class TypeTranslationError(Exception):
    """Exception raised when an expression is not valid as a type."""


def expr_to_unanalyzed_type(expr: Expression) -> Type:
    """Translate an expression to the corresponding type.

    The result is not semantically analyzed. It can be UnboundType or TypeList.
    Raise TypeTranslationError if the expression cannot represent a type.
    """
    if isinstance(expr, NameExpr):
        name = expr.name
        return UnboundType(name, line=expr.line, column=expr.column)
    elif isinstance(expr, MemberExpr):
        fullname = get_member_expr_fullname(expr)
        if fullname:
            return UnboundType(fullname, line=expr.line, column=expr.column)
        else:
            raise TypeTranslationError()
    elif isinstance(expr, IndexExpr):
        base = expr_to_unanalyzed_type(expr.base)
        if isinstance(base, UnboundType):
            if base.args:
                raise TypeTranslationError()
            if isinstance(expr.index, TupleExpr):
                args = expr.index.items
            else:
                args = [expr.index]
            base.args = [expr_to_unanalyzed_type(arg) for arg in args]
            if not base.args:
                base.empty_tuple_index = True
            return base
        else:
            raise TypeTranslationError()
    elif isinstance(expr, ListExpr):
        return TypeList([expr_to_unanalyzed_type(t) for t in expr.items],
                        line=expr.line, column=expr.column)
    elif isinstance(expr, (StrExpr, BytesExpr, UnicodeExpr)):
        # Parse string literal type.
        try:
            result = parse_str_as_type(expr.value, expr.line)
        except TypeParseError:
            raise TypeTranslationError()
        return result
    elif isinstance(expr, EllipsisExpr):
        return EllipsisType(expr.line)
    else:
        raise TypeTranslationError()


def get_member_expr_fullname(expr: MemberExpr) -> str:
    """Return the qualified name representation of a member expression.

    Return a string of form foo.bar, foo.bar.baz, or similar, or None if the
    argument cannot be represented in this form.
    """
    if isinstance(expr.expr, NameExpr):
        initial = expr.expr.name
    elif isinstance(expr.expr, MemberExpr):
        initial = get_member_expr_fullname(expr.expr)
    else:
        return None
    return '{}.{}'.format(initial, expr.name)
