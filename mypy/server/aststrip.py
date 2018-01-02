"""Strip AST from semantic information.

This is used in fine-grained incremental checking to reprocess existing AST nodes.
"""

import contextlib
from typing import Union, Iterator, Optional

from mypy.nodes import (
    Node, FuncDef, NameExpr, MemberExpr, RefExpr, MypyFile, FuncItem, ClassDef, AssignmentStmt,
    ImportFrom, Import, TypeInfo, SymbolTable, Var, CallExpr, Decorator, OverloadedFuncDef,
    SuperExpr, UNBOUND_IMPORTED, GDEF, MDEF
)
from mypy.traverser import TraverserVisitor


def strip_target(node: Union[MypyFile, FuncItem, OverloadedFuncDef]) -> None:
    """Strip a fine-grained incremental mode target from semantic information."""
    visitor = NodeStripVisitor()
    if isinstance(node, MypyFile):
        visitor.strip_file_top_level(node)
    else:
        node.accept(visitor)


class NodeStripVisitor(TraverserVisitor):
    def __init__(self) -> None:
        self.type = None  # type: Optional[TypeInfo]
        self.names = None  # type: Optional[SymbolTable]
        self.is_class_body = False
        # By default, process function definitions. If False, don't -- this is used for
        # processing module top levels.
        self.recurse_into_functions = True

    def strip_file_top_level(self, file_node: MypyFile) -> None:
        """Strip a module top-level (don't recursive into functions)."""
        self.names = file_node.names
        self.recurse_into_functions = False
        file_node.accept(self)

    def visit_class_def(self, node: ClassDef) -> None:
        """Strip class body and type info, but don't strip methods."""
        node.info.type_vars = []
        node.info.bases = []
        node.info.abstract_attributes = []
        node.info.mro = []
        node.info.add_type_vars()
        node.info._cache = set()
        node.info._cache_proper = set()
        node.base_type_exprs.extend(node.removed_base_type_exprs)
        node.removed_base_type_exprs = []
        with self.enter_class(node.info):
            super().visit_class_def(node)

    def visit_func_def(self, node: FuncDef) -> None:
        if not self.recurse_into_functions:
            return
        node.expanded = []
        node.type = node.unanalyzed_type
        with self.enter_method(node.info) if node.info else nothing():
            super().visit_func_def(node)

    def visit_decorator(self, node: Decorator) -> None:
        node.var.type = None
        for expr in node.decorators:
            expr.accept(self)
        if self.recurse_into_functions:
            node.func.accept(self)

    def visit_overloaded_func_def(self, node: OverloadedFuncDef) -> None:
        if not self.recurse_into_functions:
            return
        if node.impl:
            # Revert change made during semantic analysis pass 2.
            assert node.items[-1] is not node.impl
            node.items.append(node.impl)
        super().visit_overloaded_func_def(node)

    @contextlib.contextmanager
    def enter_class(self, info: TypeInfo) -> Iterator[None]:
        # TODO: Update and restore self.names
        old_type = self.type
        old_is_class_body = self.is_class_body
        self.type = info
        self.is_class_body = True
        yield
        self.type = old_type
        self.is_class_body = old_is_class_body

    @contextlib.contextmanager
    def enter_method(self, info: TypeInfo) -> Iterator[None]:
        # TODO: Update and restore self.names
        old_type = self.type
        old_is_class_body = self.is_class_body
        self.type = info
        self.is_class_body = False
        yield
        self.type = old_type
        self.is_class_body = old_is_class_body

    def visit_assignment_stmt(self, node: AssignmentStmt) -> None:
        node.type = node.unanalyzed_type
        if self.type and not self.is_class_body:
            # TODO: Handle multiple assignment
            if len(node.lvalues) == 1:
                lvalue = node.lvalues[0]
                if isinstance(lvalue, MemberExpr) and lvalue.is_new_def:
                    # Remove defined attribute from the class symbol table. If is_new_def is
                    # true for a MemberExpr, we know that it must be an assignment through
                    # self, since only those can define new attributes.
                    del self.type.names[lvalue.name]
        super().visit_assignment_stmt(node)

    def visit_import_from(self, node: ImportFrom) -> None:
        if node.assignments:
            node.assignments = []
        else:
            if self.names:
                # Reset entries in the symbol table. This is necessary since
                # otherwise the semantic analyzer will think that the import
                # assigns to an existing name instead of defining a new one.
                for name, as_name in node.names:
                    imported_name = as_name or name
                    symnode = self.names[imported_name]
                    symnode.kind = UNBOUND_IMPORTED
                    symnode.node = None

    def visit_import(self, node: Import) -> None:
        if node.assignments:
            node.assignments = []
        else:
            if self.names:
                # Reset entries in the symbol table. This is necessary since
                # otherwise the semantic analyzer will think that the import
                # assigns to an existing name instead of defining a new one.
                for name, as_name in node.ids:
                    imported_name = as_name or name
                    initial = imported_name.split('.')[0]
                    symnode = self.names[initial]
                    symnode.kind = UNBOUND_IMPORTED
                    symnode.node = None

    def visit_name_expr(self, node: NameExpr) -> None:
        # Global assignments are processed in semantic analysis pass 1, and we
        # only want to strip changes made in passes 2 or later.
        if not (node.kind == GDEF and node.is_new_def):
            # Remove defined attributes so that they can recreated during semantic analysis.
            if node.kind == MDEF and node.is_new_def:
                self.strip_class_attr(node.name)
            self.strip_ref_expr(node)

    def visit_member_expr(self, node: MemberExpr) -> None:
        self.strip_ref_expr(node)
        # These need to cleared for member expressions but not for other RefExprs since
        # these can change based on changed in a base class.
        node.is_new_def = False
        node.is_inferred_def = False
        if self.is_duplicate_attribute_def(node):
            # This is marked as an instance variable definition but a base class
            # defines an attribute with the same name, and we can't have
            # multiple definitions for an attribute. Defer to the base class
            # definition.
            self.strip_class_attr(node.name)
            node.def_var = None
        super().visit_member_expr(node)

    def strip_class_attr(self, name: str) -> None:
        if self.type is not None:
            del self.type.names[name]

    def is_duplicate_attribute_def(self, node: MemberExpr) -> bool:
        if not node.is_inferred_def:
            return False
        assert self.type is not None, "Internal error: Member defined outside class"
        if node.name not in self.type.names:
            return False
        return any(info.get(node.name) is not None for info in self.type.mro[1:])

    def strip_ref_expr(self, node: RefExpr) -> None:
        node.kind = None
        node.node = None
        node.fullname = None
        node.is_new_def = False
        node.is_inferred_def = False

    def visit_call_expr(self, node: CallExpr) -> None:
        node.analyzed = None
        super().visit_call_expr(node)

    def visit_super_expr(self, node: SuperExpr) -> None:
        node.info = None
        super().visit_super_expr(node)

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
