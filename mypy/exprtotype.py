"""Translate an Expression to a Type value."""

from mypy.nodes import (
    Expression, NameExpr, MemberExpr, IndexExpr, TupleExpr,
    ListExpr, StrExpr, BytesExpr, UnicodeExpr, EllipsisExpr, CallExpr,
    ARG_POS, ARG_NAMED, get_member_expr_fullname
)
from mypy.sharedparse import ARG_KINDS_BY_CONSTRUCTOR, STAR_ARG_CONSTRUCTORS
from mypy.fastparse import parse_type_comment
from mypy.types import Type, UnboundType, ArgumentList, EllipsisType, AnyType, Optional


class TypeTranslationError(Exception):
    """Exception raised when an expression is not valid as a type."""


def _extract_str(expr: Expression) -> Optional[str]:
    if isinstance(expr, NameExpr) and expr.name == 'None':
        return None
    elif isinstance(expr, StrExpr):
        return expr.value
    else:
        raise TypeTranslationError()


def expr_to_unanalyzed_type(expr: Expression) -> Type:
    """Translate an expression to the corresponding type.

    The result is not semantically analyzed. It can be UnboundType or ArgumentList.
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
        types = []  # type: List[Type]
        names = []  # type: List[Optional[str]]
        kinds = []  # type: List[int]
        for it in expr.items:
            if isinstance(it, CallExpr):
                if not isinstance(it.callee, NameExpr):
                    raise TypeTranslationError()
                arg_const = it.callee.name
                try:
                    kind = ARG_KINDS_BY_CONSTRUCTOR[arg_const]
                except KeyError:
                    raise TypeTranslationError()
                name = None
                typ = AnyType(implicit=True)  # type: Type
                star = arg_const in STAR_ARG_CONSTRUCTORS
                for i, arg in enumerate(it.args):
                    if it.arg_names[i] is not None:
                        if it.arg_names[i] == "name":
                            name = _extract_str(arg)
                            continue
                        elif it.arg_names[i] == "typ":
                            typ = expr_to_unanalyzed_type(arg)
                            continue
                        else:
                            raise TypeTranslationError()
                    elif i == 0 and not star:
                        name = _extract_str(arg)
                    elif i == 1 and not star or i == 0 and star:
                        typ = expr_to_unanalyzed_type(arg)
                    else:
                        raise TypeTranslationError()
                names.append(name)
                types.append(typ)
                kinds.append(kind)
            else:
                types.append(expr_to_unanalyzed_type(it))
                names.append(None)
                kinds.append(ARG_POS)
        return ArgumentList(types, names, kinds,
                        line=expr.line, column=expr.column)
    elif isinstance(expr, (StrExpr, BytesExpr, UnicodeExpr)):
        # Parse string literal type.
        try:
            result = parse_type_comment(expr.value, expr.line, None)
        except SyntaxError:
            raise TypeTranslationError()
        return result
    elif isinstance(expr, EllipsisExpr):
        return EllipsisType(expr.line)
    else:
        raise TypeTranslationError()
