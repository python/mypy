"""Strip AST from from semantic and type information."""

from typing import Union

from mypy.nodes import (
    Node, FuncDef, NameExpr, MemberExpr, RefExpr, MypyFile, FuncItem, ClassDef, AssignmentStmt
)
from mypy.traverser import TraverserVisitor


def strip_target(node: Union[MypyFile, FuncItem]) -> None:
    NodeStripVisitor().strip_target(node)


class NodeStripVisitor(TraverserVisitor):
    def strip_target(self, node: Union[MypyFile, FuncItem]) -> None:
        """Strip a fine-grained incremental mode target."""
        if isinstance(node, MypyFile):
            self.strip_top_level(node)
        else:
            node.accept(self)

    def strip_top_level(self, file_node: MypyFile) -> None:
        """Strip a module top-level (don't recursive into functions)."""
        for node in file_node.defs:
            if not isinstance(node, (FuncItem, ClassDef)):
                node.accept(self)

    def visit_func_def(self, node: FuncDef) -> None:
        node.expanded = []
        node.type = node.unanalyzed_type
        super().visit_func_def(node)

    def visit_assignment_stmt(self, node: AssignmentStmt) -> None:
        node.type = node.unanalyzed_type
        super().visit_assignment_stmt(node)

    def visit_name_expr(self, node: NameExpr) -> None:
        self.visit_ref_expr(node)

    def visit_member_expr(self, node: MemberExpr) -> None:
        self.visit_ref_expr(node)

    def visit_ref_expr(self, node: RefExpr) -> None:
        node.kind = None
        node.node = None
        node.fullname = None

    # TODO: handle more node types
