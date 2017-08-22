"""Merge a new version of a module AST to an old version.

See the main entry point merge_asts for details.
"""

from typing import Dict, List, cast, TypeVar, Optional

from mypy.nodes import (
    Node, MypyFile, SymbolTable, Block, AssignmentStmt, NameExpr, MemberExpr, RefExpr, TypeInfo,
    FuncDef, ClassDef, SymbolNode, Var, Statement, MDEF
)
from mypy.traverser import TraverserVisitor
from mypy.types import (
    Type, TypeVisitor, Instance, AnyType, NoneTyp, CallableType, DeletedType, PartialType,
    TupleType, TypeType, TypeVarType, TypedDictType, UnboundType, UninhabitedType, UnionType,
    Overloaded
)


def merge_asts(old: MypyFile, old_symbols: SymbolTable,
               new: MypyFile, new_symbols: SymbolTable) -> None:
    """Merge a new version of a module AST to a previous version.

    The main idea is to preserve the identities of externally visible
    nodes in the old AST (that have a corresponding node in the new AST).
    All old node state (outside identity) will come from the new AST.

    When this returns, 'old' will refer to the merged AST, but 'new_symbols'
    will be the new symbol table. 'new' and 'old_symbols' will no longer be
    valid.
    """
    assert new.fullname() == old.fullname()
    replacement_map = replacement_map_from_symbol_table(
        old_symbols, new_symbols, prefix=old.fullname())
    replacement_map[new] = old
    node = replace_nodes_in_ast(new, replacement_map)
    assert node is old
    replace_nodes_in_symbol_table(new_symbols, replacement_map)


def replacement_map_from_symbol_table(
        old: SymbolTable, new: SymbolTable, prefix: str) -> Dict[SymbolNode, SymbolNode]:
    replacements = {}  # type: Dict[SymbolNode, SymbolNode]
    for name, node in old.items():
        if (name in new and (node.kind == MDEF
                             or node.node and get_prefix(node.node.fullname()) == prefix)):
            new_node = new[name]
            if (type(new_node.node) == type(node.node)  # noqa
                    and new_node.node and node.node and
                    new_node.node.fullname() == node.node.fullname() and
                    new_node.kind == node.kind):
                replacements[new_node.node] = node.node
                if isinstance(node.node, TypeInfo) and isinstance(new_node.node, TypeInfo):
                    type_repl = replacement_map_from_symbol_table(
                        node.node.names,
                        new_node.node.names,
                        prefix)
                    replacements.update(type_repl)
    return replacements


def replace_nodes_in_ast(node: SymbolNode,
                         replacements: Dict[SymbolNode, SymbolNode]) -> SymbolNode:
    visitor = NodeReplaceVisitor(replacements)
    node.accept(visitor)
    return replacements.get(node, node)


SN = TypeVar('SN', bound=SymbolNode)


class NodeReplaceVisitor(TraverserVisitor):
    """Transform some nodes to new identities in an AST.

    Only nodes that live in the symbol table may be
    replaced, which simplifies the implementation some.
    """

    def __init__(self, replacements: Dict[SymbolNode, SymbolNode]) -> None:
        self.replacements = replacements

    def visit_mypy_file(self, node: MypyFile) -> None:
        node = self.fixup(node)
        node.defs = self.replace_statements(node.defs)
        super().visit_mypy_file(node)

    def visit_block(self, node: Block) -> None:
        super().visit_block(node)
        node.body = self.replace_statements(node.body)

    def visit_func_def(self, node: FuncDef) -> None:
        node = self.fixup(node)
        if node.type:
            self.fixup_type(node.type)
        super().visit_func_def(node)

    def visit_class_def(self, node: ClassDef) -> None:
        # TODO additional things like the MRO
        node.defs.body = self.replace_statements(node.defs.body)
        replace_nodes_in_symbol_table(node.info.names, self.replacements)
        info = node.info
        for i, item in enumerate(info.mro):
            info.mro[i] = self.fixup(info.mro[i])
        for i, base in enumerate(info.bases):
            self.fixup_type(info.bases[i])
        super().visit_class_def(node)

    def visit_assignment_stmt(self, node: AssignmentStmt) -> None:
        if node.type:
            self.fixup_type(node.type)
        super().visit_assignment_stmt(node)

    # Expressions

    def visit_name_expr(self, node: NameExpr) -> None:
        self.visit_ref_expr(node)

    def visit_member_expr(self, node: MemberExpr) -> None:
        self.visit_ref_expr(node)
        super().visit_member_expr(node)

    def visit_ref_expr(self, node: RefExpr) -> None:
        if node.node is not None:
            node.node = self.fixup(node.node)

    # Helpers

    def fixup(self, node: SN) -> SN:
        if node in self.replacements:
            new = self.replacements[node]
            new.__dict__ = node.__dict__
            return cast(SN, new)
        return node

    def fixup_type(self, typ: Type) -> None:
        typ.accept(TypeReplaceVisitor(self.replacements))

    def replace_statements(self, nodes: List[Statement]) -> List[Statement]:
        result = []
        for node in nodes:
            if isinstance(node, SymbolNode):
                node = self.fixup(node)
            result.append(node)
        return result


class TypeReplaceVisitor(TypeVisitor[None]):
    def __init__(self, replacements: Dict[SymbolNode, SymbolNode]) -> None:
        self.replacements = replacements

    def visit_instance(self, typ: Instance) -> None:
        typ.type = self.fixup(typ.type)
        for arg in typ.args:
            arg.accept(self)

    def visit_any(self, typ: AnyType) -> None:
        pass

    def visit_none_type(self, typ: NoneTyp) -> None:
        pass

    def visit_callable_type(self, typ: CallableType) -> None:
        for arg in typ.arg_types:
            arg.accept(self)
        typ.ret_type.accept(self)
        # TODO: typ.definition
        # TODO: typ.fallback
        assert not typ.variables  # TODO

    def visit_overloaded(self, t: Overloaded) -> None:
        raise NotImplementedError

    def visit_deleted_type(self, typ: DeletedType) -> None:
        pass

    def visit_partial_type(self, typ: PartialType) -> None:
        raise RuntimeError

    def visit_tuple_type(self, typ: TupleType) -> None:
        raise NotImplementedError

    def visit_type_type(self, typ: TypeType) -> None:
        raise NotImplementedError

    def visit_type_var(self, typ: TypeVarType) -> None:
        raise NotImplementedError

    def visit_typeddict_type(self, typ: TypedDictType) -> None:
        raise NotImplementedError

    def visit_unbound_type(self, typ: UnboundType) -> None:
        raise RuntimeError

    def visit_uninhabited_type(self, typ: UninhabitedType) -> None:
        pass

    def visit_union_type(self, typ: UnionType) -> None:
        raise NotImplementedError

    # Helpers

    def fixup(self, node: SN) -> SN:
        if node in self.replacements:
            new = self.replacements[node]
            new.__dict__ = node.__dict__
            return cast(SN, new)
        return node


def replace_nodes_in_symbol_table(symbols: SymbolTable,
                                  replacements: Dict[SymbolNode, SymbolNode]) -> None:
    for name, node in symbols.items():
        if node.node and node.node in replacements:
            new = replacements[node.node]
            new.__dict__ = node.node.__dict__
            node.node = new
            if isinstance(node.node, Var) and node.node.type:
                node.node.type.accept(TypeReplaceVisitor(replacements))
                node.node.info = cast(TypeInfo, replacements.get(node.node.info, node.node.info))


def get_prefix(fullname: str) -> str:
    """Drop the final component of a qualified name (e.g. ('x.y' -> 'x')."""
    return fullname.rsplit('.', 1)[0]
