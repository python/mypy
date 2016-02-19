"""Fix up various things after deserialization()."""

from typing import Dict, cast

from mypy.nodes import (MypyFile, SymbolTable, SymbolTableNode, TypeInfo, Var,
                        LDEF, MDEF, GDEF, MODULE_REF)
from mypy.types import Instance, CallableType


def lookup_qualified(name: str, modules: Dict[str, MypyFile]) -> SymbolTableNode:
    parts = name.split('.')
    # print('  Looking for module', parts)
    node = modules.get(parts[0])
    if node is None:
        print('*** Cannot find module', parts[0])
        return None
    for i, part in enumerate(parts[1:-1], 1):
        # print('  Looking for submodule', part, 'of package', parts[:i])
        if part not in node.names:
            print('*** Cannot find submodule', part, 'of package', parts[:i])
            return None
        if node.names[part].node is None:
            print('*** Weird!!!', part, 'exists in', parts[:i], 'but its node is None')
            return None
        node = cast(MypyFile, node.names[part].node)
        assert isinstance(node, MypyFile), node
    # print('  Looking for', parts[-1], 'in module', parts[:-1])
    res = node.names.get(parts[-1])
    if res is None:
        print('*** Cannot find', parts[-1], 'in module', parts[:-1])
    return res


def fixup_symbol_table(symtab: SymbolTable, modules: Dict[str, MypyFile]) -> None:
    for key, value in symtab.items():
        if value.kind in (LDEF, MDEF, GDEF):
            if isinstance(value.node, Var):
                fixup_var(value.node, modules)
        elif value.kind == MODULE_REF:
            if value.module_ref not in modules:
                print('*** Cannot find module', value.module_ref, 'needed for patch-up')
                return
            value.node = modules[value.module_ref]
            # print('Fixed up module ref to', value.module_ref)


def fixup_var(node: Var, modules: Dict[str, MypyFile]) -> None:
    if isinstance(node.type, Instance):
        if isinstance(node.type.type, TypeInfo):
            if node.type.type.is_dummy:
                fn = node.type.type.fullname()
                stnode = lookup_qualified(fn, modules)
                if stnode is None:
                    print('*** Cannot find', fn, 'needed to fix up', node)
                    return
                assert stnode is not None and stnode.kind == GDEF, stnode
                if isinstance(stnode.node, TypeInfo):
                    node.type.type = stnode.node
                    # print('Fixed up type for', node, 'from', stnode.node.fullname())
                else:
                    assert False, stnode.node
                return
