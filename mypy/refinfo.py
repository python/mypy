"""Find line-level reference information from a mypy AST (undocumented feature)"""

from __future__ import annotations

from mypy.nodes import LDEF, MemberExpr, MypyFile, NameExpr, RefExpr
from mypy.traverser import TraverserVisitor


class RefInfoVisitor(TraverserVisitor):
    def __init__(self) -> None:
        super().__init__()
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
        elif isinstance(expr, MemberExpr) and not expr.fullname:
            fullname = f"*.{expr.name}"
        if fullname is not None:
            self.data.append({"line": expr.line, "column": expr.column, "target": fullname})


def get_undocumented_ref_info_json(tree: MypyFile) -> list[dict[str, object]]:
    visitor = RefInfoVisitor()
    tree.accept(visitor)
    return visitor.data
