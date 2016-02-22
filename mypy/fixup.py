"""Fix up various things after deserialization()."""

# TODO: Handle import cycles better. Once several modules are all
# loaded, keep fixing them up until they are all fixed 100%.  (This
# requires adding logic to build.py.)

# TODO: Fix up info everywhere it occurs.

from typing import Any, Dict, cast

from mypy.nodes import (MypyFile, SymbolTable, SymbolTableNode,
                        TypeInfo, FuncDef, OverloadedFuncDef, Var,
                        LDEF, MDEF, GDEF, MODULE_REF)
from mypy.types import Instance, CallableType, TypeVisitor
from mypy.visitor import NodeVisitor


def fixup_symbol_table(symtab: SymbolTable, modules: Dict[str, MypyFile],
                       info: TypeInfo = None, visitor: 'NodeFixer' = None) -> None:
    if visitor is None:
        visitor = NodeFixer(modules)
    for key, value in symtab.items():
        if value.kind in (LDEF, MDEF, GDEF):
            if isinstance(value.node, TypeInfo):
                print('Descending', value.node.fullname())
                if value.node.names is not None:
                    fixup_symbol_table(value.node.names, modules, value.node, visitor)
                if value.node._promote is not None:
                    value.node._promote.accept(visitor.type_fixer)
                print("Calculating mro for", value.node.fullname())
                value.node.calculate_mro()
            elif value.node is not None:
                value.node.accept(visitor)
        elif value.kind == MODULE_REF:
            if value.module_ref not in modules:
                print('*** Cannot find module', value.module_ref, 'needed for patch-up')
                return
            value.node = modules[value.module_ref]
            # print('Fixed up module ref to', value.module_ref)
        # TODO: Other kinds?


class NodeFixer(NodeVisitor[None]):
    def __init__(self, modules: Dict[str, MypyFile]) -> None:
        self.modules = modules
        self.type_fixer = TypeFixer(self.modules)

    def visit_func_def(self, func: FuncDef) -> None:
        if func.type is not None:
            func.type.accept(self.type_fixer)
        for arg in func.arguments:
            if arg.type_annotation is not None:
                arg.type_annotation.accept(self.type_fixer)
        # TODO: Also fix up func.info here?

    def visit_overloaded_func_def(self, over: OverloadedFuncDef) -> None:
        # TODO: Fix up func.info here?
        pass

    def visit_var(self, v: Var) -> None:
        if v.type is not None:
            v.type.accept(self.type_fixer)


class TypeFixer(TypeVisitor[None]):
    def __init__(self, modules: Dict[str, MypyFile]) -> None:
        self.modules = modules

    def visit_instance(self, inst: Instance) -> None:
        # TODO: Combine Instances that are exactly the same?
        type_ref = inst.type_ref
        if type_ref is not None:
            del inst.type_ref
            stnode =lookup_qualified(type_ref, self.modules)
            if stnode is not None and isinstance(stnode.node, TypeInfo):
                inst.type = stnode.node

    # TODO: Why are these abstract?

    def visit_any(self, o: Any) -> None:
        pass

    def visit_callable_type(self, o: Any) -> None:
        pass

    def visit_deleted_type(self, o: Any) -> None:
        pass

    def visit_none_type(self, o: Any) -> None:
        pass

    def visit_partial_type(self, o: Any) -> None:
        pass

    def visit_tuple_type(self, o: Any) -> None:
        pass

    def visit_type_var(self, o: Any) -> None:
        pass

    def visit_unbound_type(self, o: Any) -> None:
        pass

    def visit_union_type(self, o: Any) -> None:
        pass

    def visit_void(self, o: Any) -> None:
        pass


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
