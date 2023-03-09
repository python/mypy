"""Find line-level reference information from a mypy AST (undocumented feature)"""

from __future__ import annotations

from mypy.nodes import LDEF, Expression, MemberExpr, MypyFile, NameExpr, RefExpr
from mypy.traverser import TraverserVisitor
from mypy.typeops import tuple_fallback
from mypy.types import (
    FunctionLike,
    Instance,
    TupleType,
    Type,
    TypeType,
    TypeVarLikeType,
    get_proper_type,
)


class RefInfoVisitor(TraverserVisitor):
    def __init__(self, type_map: dict[Expression, Type]) -> None:
        super().__init__()
        self.type_map = type_map
        self.data: list[dict[str, object]] = []

    def visit_name_expr(self, expr: NameExpr) -> None:
        super().visit_name_expr(expr)
        self.record_ref_expr(expr)

    def visit_member_expr(self, expr: MemberExpr) -> None:
        super().visit_member_expr(expr)
        self.record_ref_expr(expr)

    def record_ref_expr(self, expr: RefExpr) -> None:
        fullname = None
        if expr.kind != LDEF and "." in expr.fullname:
            fullname = expr.fullname
        elif isinstance(expr, MemberExpr):
            typ = self.type_map.get(expr.expr)
            if typ:
                tfn = type_fullname(typ)
                if tfn:
                    fullname = f"{tfn}.{expr.name}"
            if not fullname:
                fullname = f"*.{expr.name}"
        if fullname is not None:
            self.data.append({"line": expr.line, "column": expr.column, "target": fullname})


def type_fullname(typ: Type) -> str | None:
    typ = get_proper_type(typ)
    if isinstance(typ, Instance):
        return typ.type.fullname
    elif isinstance(typ, TypeType):
        return type_fullname(typ.item)
    elif isinstance(typ, FunctionLike) and typ.is_type_obj():
        return type_fullname(typ.fallback)
    elif isinstance(typ, TupleType):
        return type_fullname(tuple_fallback(typ))
    elif isinstance(typ, TypeVarLikeType):
        return type_fullname(typ.upper_bound)
    return None


def get_undocumented_ref_info_json(
    tree: MypyFile, type_map: dict[Expression, Type]
) -> list[dict[str, object]]:
    visitor = RefInfoVisitor(type_map)
    tree.accept(visitor)
    return visitor.data
