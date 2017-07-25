"""Strip AST from semantic information."""

import contextlib
from typing import Union, Iterator, Optional

from mypy.nodes import (
    Node, FuncDef, NameExpr, MemberExpr, RefExpr, MypyFile, FuncItem, ClassDef, AssignmentStmt,
    TypeInfo, Var
)
from mypy.traverser import TraverserVisitor


def strip_target(node: Union[MypyFile, FuncItem]) -> None:
    NodeStripVisitor().strip_target(node)


class NodeStripVisitor(TraverserVisitor):
    def __init__(self) -> None:
        self.type = None  # type: Optional[TypeInfo]

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
            elif isinstance(node, ClassDef):
                self.strip_class_body(node)

    def strip_class_body(self, node: ClassDef) -> None:
        """Strip class body and type info, but don't strip methods."""
        node.info.type_vars = []
        node.info.bases = []
        node.info.abstract_attributes = []
        node.info.mro = []
        node.info.add_type_vars()

    def visit_func_def(self, node: FuncDef) -> None:
        node.expanded = []
        node.type = node.unanalyzed_type
        with self.enter_class(node.info) if node.info else nothing():
            super().visit_func_def(node)

    @contextlib.contextmanager
    def enter_class(self, info: TypeInfo) -> Iterator[None]:
        old = self.type
        self.type = info
        yield
        self.type = old

    def visit_assignment_stmt(self, node: AssignmentStmt) -> None:
        node.type = node.unanalyzed_type
        super().visit_assignment_stmt(node)

    def visit_name_expr(self, node: NameExpr) -> None:
        self.strip_ref_expr(node)

    def visit_member_expr(self, node: MemberExpr) -> None:
        self.strip_ref_expr(node)
        if self.is_duplicate_attribute_def(node):
            # This is marked as an instance variable definition but a base class
            # defines an attribute with the same name, and we can't have
            # multiple definitions for an attribute. Defer to the base class
            # definition.
            if self.type is not None:
                del self.type.names[node.name]
            node.is_def = False
            node.def_var = None

    def is_duplicate_attribute_def(self, node: MemberExpr) -> bool:
        if not node.is_def:
            return False
        assert self.type is not None, "Internal error: Member defined outside class"
        if node.name not in self.type.names:
            return False
        return any(info.get(node.name) is not None for info in self.type.mro[1:])

    def strip_ref_expr(self, node: RefExpr) -> None:
        node.kind = None
        node.node = None
        node.fullname = None

    # TODO: handle more node types


def is_self_member_ref(memberexpr: MemberExpr) -> bool:
    """Does memberexpr refer to an attribute of self?"""
    # TODO: Merge with is_self_member_ref in semanal.py.
    if not isinstance(memberexpr.expr, NameExpr):
        return False
    node = memberexpr.expr.node
    return isinstance(node, Var) and node.is_self


@contextlib.contextmanager
def nothing() -> Iterator[None]:
    yield
