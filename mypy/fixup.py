"""Fix up various things after deserialization()."""

from typing import Dict, cast

from mypy.nodes import MypyFile, SymbolTable, SymbolTableNode, TypeInfo, Var, LDEF, MDEF, GDEF, MODULE_REF
from mypy.types import Instance, CallableType


def lookup_qualified(name: str, modules: Dict[str, MypyFile]) -> SymbolTableNode:
    parts = name.split('.')
    node = modules.get(parts[0])
    if node is None:
        return None
    for part in parts[1:-1]:
        if part not in node.names:
            return None
        node = cast(MypyFile, node.names[part].node)
        assert isinstance(node, MypyFile)
    return node.names.get(parts[-1])


def fixup_symbol_table(symtab: SymbolTable, modules: Dict[str, MypyFile]) -> None:
    for key, value in symtab.items():
        if value.kind in (LDEF, MDEF, GDEF):
            if isinstance(value.node, Var):
                fixup_var(value.node, modules)


def fixup_var(node: Var, modules: Dict[str, MypyFile]) -> None:
    if isinstance(node.type, Instance):
        if isinstance(node.type.type, TypeInfo):
            if node.type.type.is_dummy:
                stnode = lookup_qualified(node.type.type.fullname(), modules)
                assert stnode is not None and stnode.kind == GDEF
                if isinstance(stnode.node, TypeInfo):
                    node.type.type = stnode.node
                    print('Fixed up type for', node, 'from', stnode.node.fullname())
                else:
                    assert False, stnode.node
                return
