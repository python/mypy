"""Strip/reset AST in-place to match state after semantic analyzer pre-analysis.

Fine-grained incremental mode reruns semantic analysis main pass
and type checking for *existing* AST nodes (targets) when changes are
propagated using fine-grained dependencies.  AST nodes attributes are
sometimes changed during semantic analysis main pass, and running
semantic analysis again on those nodes would produce incorrect
results, since this pass isn't idempotent. This pass resets AST
nodes to reflect the state after semantic pre-analysis, so that we
can rerun semantic analysis.
(The above is in contrast to behavior with modules that have source code
changes, for which we re-parse the entire module and reconstruct a fresh
AST. No stripping is required in this case. Both modes of operation should
have the same outcome.)
Notes:
* This is currently pretty fragile, as we must carefully undo whatever
  changes can be made in semantic analysis main pass, including changes
  to symbol tables.
* We reuse existing AST nodes because it makes it relatively straightforward
  to reprocess only a single target within a module efficiently. If there
  was a way to parse a single target within a file, in time proportional to
  the size of the target, we'd rather create fresh AST nodes than strip them.
  (This is possible only in Python 3.8+)
* Currently we don't actually reset all changes, but only those known to affect
  non-idempotent semantic analysis behavior.
  TODO: It would be more principled and less fragile to reset everything
      changed in semantic analysis main pass and later.
* Reprocessing may recreate AST nodes (such as Var nodes, and TypeInfo nodes
  created with assignment statements) that will get different identities from
  the original AST. Thus running an AST merge is necessary after stripping,
  even though some identities are preserved.
"""

import contextlib
from typing import Union, Iterator, Optional, Dict, Tuple

from mypy.nodes import (
    FuncDef, NameExpr, MemberExpr, RefExpr, MypyFile, ClassDef, AssignmentStmt,
    ImportFrom, CallExpr, Decorator, OverloadedFuncDef, Node, TupleExpr, ListExpr,
    SuperExpr, IndexExpr, ImportAll, ForStmt, Block, CLASSDEF_NO_INFO, TypeInfo,
    StarExpr, Var, SymbolTableNode
)
from mypy.traverser import TraverserVisitor
from mypy.types import CallableType
from mypy.typestate import TypeState


SavedAttributes = Dict[Tuple[ClassDef, str], SymbolTableNode]


def strip_target(node: Union[MypyFile, FuncDef, OverloadedFuncDef],
                 saved_attrs: SavedAttributes) -> None:
    """Reset a fine-grained incremental target to state before main pass of semantic analysis.

    The most notable difference from the old version of strip_target() is that new semantic
    analyzer doesn't have first pass where Vars and TypeInfos are pre-populated, so the stripping
    is more thorough: all TypeInfos are killed. Therefore we need to preserve the variables
    defined as attributes on self. This is done by patches (callbacks) returned from this function
    that re-add these variables when called.

    Args:
        node: node to strip
        saved_attrs: collect attributes here that may need to be re-added to
            classes afterwards if stripping a class body (this dict is mutated)
    """
    visitor = NodeStripVisitor(saved_attrs)
    if isinstance(node, MypyFile):
        visitor.strip_file_top_level(node)
    else:
        node.accept(visitor)


class NodeStripVisitor(TraverserVisitor):
    def __init__(self, saved_class_attrs: SavedAttributes) -> None:
        # The current active class.
        self.type = None  # type: Optional[TypeInfo]
        # This is True at class scope, but not in methods.
        self.is_class_body = False
        # By default, process function definitions. If False, don't -- this is used for
        # processing module top levels.
        self.recurse_into_functions = True
        # These attributes were removed from top-level classes during strip and
        # will be added afterwards (if no existing definition is found). These
        # must be added back before semantically analyzing any methods.
        self.saved_class_attrs = saved_class_attrs

    def strip_file_top_level(self, file_node: MypyFile) -> None:
        """Strip a module top-level (don't recursive into functions)."""
        self.recurse_into_functions = False
        file_node.plugin_deps.clear()
        file_node.accept(self)
        for name in file_node.names.copy():
            # TODO: this is a hot fix, we should delete all names,
            # see https://github.com/python/mypy/issues/6422.
            if '@' not in name:
                del file_node.names[name]

    def visit_block(self, b: Block) -> None:
        if b.is_unreachable:
            return
        super().visit_block(b)

    def visit_class_def(self, node: ClassDef) -> None:
        """Strip class body and type info, but don't strip methods."""
        # We need to save the implicitly defined instance variables,
        # i.e. those defined as attributes on self. Otherwise, they would
        # be lost if we only reprocess top-levels (this kills TypeInfos)
        # but not the methods that defined those variables.
        if not self.recurse_into_functions:
            self.save_implicit_attributes(node)
        # We need to delete any entries that were generated by plugins,
        # since they will get regenerated.
        to_delete = {v.node for v in node.info.names.values() if v.plugin_generated}
        node.type_vars = []
        node.base_type_exprs.extend(node.removed_base_type_exprs)
        node.removed_base_type_exprs = []
        node.defs.body = [s for s in node.defs.body
                          if s not in to_delete]
        with self.enter_class(node.info):
            super().visit_class_def(node)
        TypeState.reset_subtype_caches_for(node.info)
        # Kill the TypeInfo, since there is none before semantic analysis.
        node.info = CLASSDEF_NO_INFO

    def save_implicit_attributes(self, node: ClassDef) -> None:
        """Produce callbacks that re-add attributes defined on self."""
        for name, sym in node.info.names.items():
            if isinstance(sym.node, Var) and sym.implicit:
                self.saved_class_attrs[node, name] = sym

    def visit_func_def(self, node: FuncDef) -> None:
        if not self.recurse_into_functions:
            return
        node.expanded = []
        node.type = node.unanalyzed_type
        if node.type:
            # Type variable binder binds type variables before the type is analyzed,
            # this causes unanalyzed_type to be modified in place. We needed to revert this
            # in order to get the state exactly as it was before semantic analysis.
            # See also #4814.
            assert isinstance(node.type, CallableType)
            node.type.variables = []
        with self.enter_method(node.info) if node.info else nothing():
            super().visit_func_def(node)

    def visit_decorator(self, node: Decorator) -> None:
        node.var.type = None
        for expr in node.decorators:
            expr.accept(self)
        if self.recurse_into_functions:
            node.func.accept(self)
        else:
            # Only touch the final status if we re-process
            # the top level, since decorators are processed there.
            node.var.is_final = False
            node.func.is_final = False

    def visit_overloaded_func_def(self, node: OverloadedFuncDef) -> None:
        if not self.recurse_into_functions:
            return
        # Revert change made during semantic analysis main pass.
        node.items = node.unanalyzed_items.copy()
        node.impl = None
        node.is_final = False
        super().visit_overloaded_func_def(node)

    def visit_assignment_stmt(self, node: AssignmentStmt) -> None:
        node.type = node.unanalyzed_type
        node.is_final_def = False
        node.is_alias_def = False
        if self.type and not self.is_class_body:
            for lvalue in node.lvalues:
                # Revert assignments made via self attributes.
                self.process_lvalue_in_method(lvalue)
        super().visit_assignment_stmt(node)

    def visit_import_from(self, node: ImportFrom) -> None:
        node.assignments = []

    def visit_import_all(self, node: ImportAll) -> None:
        node.assignments = []

    def visit_for_stmt(self, node: ForStmt) -> None:
        node.index_type = node.unanalyzed_index_type
        node.inferred_item_type = None
        node.inferred_iterator_type = None
        super().visit_for_stmt(node)

    def visit_name_expr(self, node: NameExpr) -> None:
        self.strip_ref_expr(node)

    def visit_member_expr(self, node: MemberExpr) -> None:
        self.strip_ref_expr(node)
        super().visit_member_expr(node)

    def visit_index_expr(self, node: IndexExpr) -> None:
        node.analyzed = None  # May have been an alias or type application.
        super().visit_index_expr(node)

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

    def process_lvalue_in_method(self, lvalue: Node) -> None:
        if isinstance(lvalue, MemberExpr):
            if lvalue.is_new_def:
                # Remove defined attribute from the class symbol table. If is_new_def is
                # true for a MemberExpr, we know that it must be an assignment through
                # self, since only those can define new attributes.
                assert self.type is not None
                del self.type.names[lvalue.name]
                key = (self.type.defn, lvalue.name)
                if key in self.saved_class_attrs:
                    del self.saved_class_attrs[key]
        elif isinstance(lvalue, (TupleExpr, ListExpr)):
            for item in lvalue.items:
                self.process_lvalue_in_method(item)
        elif isinstance(lvalue, StarExpr):
            self.process_lvalue_in_method(lvalue.expr)

    @contextlib.contextmanager
    def enter_class(self, info: TypeInfo) -> Iterator[None]:
        old_type = self.type
        old_is_class_body = self.is_class_body
        self.type = info
        self.is_class_body = True
        yield
        self.type = old_type
        self.is_class_body = old_is_class_body

    @contextlib.contextmanager
    def enter_method(self, info: TypeInfo) -> Iterator[None]:
        old_type = self.type
        old_is_class_body = self.is_class_body
        self.type = info
        self.is_class_body = False
        yield
        self.type = old_type
        self.is_class_body = old_is_class_body


@contextlib.contextmanager
def nothing() -> Iterator[None]:
    yield
