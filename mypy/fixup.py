"""Fix up various things after deserialization.

Also clean up a few things before serialization.
"""

from typing import Any, Dict, Optional, cast

from mypy.nodes import (MypyFile, SymbolNode, SymbolTable, SymbolTableNode,
                        TypeInfo, FuncDef, OverloadedFuncDef, Decorator, Var,
                        LDEF, MDEF, GDEF, MODULE_REF)
from mypy.types import (CallableType, EllipsisType, Instance, Overloaded, TupleType,
                        TypeList, TypeVarType, UnboundType, UnionType, TypeVisitor)
from mypy.visitor import NodeVisitor


def cleanup_module(tree: MypyFile, modules: Dict[str, MypyFile]) -> None:
    # print("Cleaning", tree.fullname())
    node_cleaner = NodeCleaner(modules)
    node_cleaner.visit_symbol_table(tree.names)


def fixup_module_pass_one(tree: MypyFile, modules: Dict[str, MypyFile]) -> None:
    assert modules[tree.fullname()] is tree
    node_fixer = NodeFixer(modules)
    node_fixer.visit_symbol_table(tree.names)
    # print('Done pass 1', tree.fullname())


def fixup_module_pass_two(tree: MypyFile, modules: Dict[str, MypyFile]) -> None:
    assert modules[tree.fullname()] is tree
    compute_all_mros(tree.names, modules)
    # print('Done pass 2', tree.fullname())


def compute_all_mros(symtab: SymbolTable, modules: Dict[str, MypyFile]) -> None:
    for key, value in symtab.items():
        if value.kind in (LDEF, MDEF, GDEF) and isinstance(value.node, TypeInfo):
            info = value.node
            # print('  Calc MRO for', info.fullname())
            info.calculate_mro()
            if not info.mro:
                print('*** No MRO calculated for', info.fullname())
            compute_all_mros(info.names, modules)


# TODO: Fix up .info when deserializing, i.e. much earlier.
class NodeFixer(NodeVisitor[None]):
    current_info = None  # type: Optional[TypeInfo]

    def __init__(self, modules: Dict[str, MypyFile], type_fixer: 'TypeFixer' = None) -> None:
        self.modules = modules
        if type_fixer is None:
            type_fixer = TypeFixer(self.modules)
        self.type_fixer = type_fixer

    # NOTE: This method isn't (yet) part of the NodeVisitor API.
    def visit_type_info(self, info: TypeInfo) -> None:
        save_info = self.current_info
        try:
            self.current_info = info
            # print('Descending into', info.fullname())
            if info.names is not None:
                self.visit_symbol_table(info.names)
            # print('Fixing up', info.fullname())
            if info.subtypes is not None:
                for st in info.subtypes:
                    self.visit_type_info(st)
            if info.bases is not None:
                for base in info.bases:
                    base.accept(self.type_fixer)
            if info._promote is not None:
                info._promote.accept(self.type_fixer)
            if info.tuple_type is not None:
                info.tuple_type.accept(self.type_fixer)
        finally:
            self.current_info = save_info

    # NOTE: This method *definitely* isn't part of the NodeVisitor API.
    def visit_symbol_table(self, symtab: SymbolTable) -> None:
        for key, value in list(symtab.items()):  # TODO: Only use list() when cleaning.
            if value.kind in (LDEF, MDEF, GDEF):
                if isinstance(value.node, TypeInfo):
                    # TypeInfo has no accept().  TODO: Add it?
                    self.visit_type_info(value.node)
                elif value.node is not None:
                    value.node.accept(self)
                if value.type is not None:
                    value.type.accept(self.type_fixer)
            elif value.kind == MODULE_REF:
                self.visit_module_ref(value)
            # TODO: Other kinds?

    # NOTE: Nor is this one.
    def visit_module_ref(self, value: SymbolTableNode):
        if value.module_ref not in self.modules:
            print('*** Cannot find module', value.module_ref, 'needed for patch-up')
            return
        value.node = self.modules[value.module_ref]

    def visit_func_def(self, func: FuncDef) -> None:
        if self.current_info is not None:
            func.info = self.current_info
        if func.type is not None:
            func.type.accept(self.type_fixer)
        for arg in func.arguments:
            if arg.type_annotation is not None:
                arg.type_annotation.accept(self.type_fixer)

    def visit_overloaded_func_def(self, func: OverloadedFuncDef) -> None:
        if self.current_info is not None:
            func.info = self.current_info
        if func.type:
            func.type.accept(self.type_fixer)

    def visit_decorator(self, d: Decorator) -> None:
        if self.current_info is not None:
            d.var.info = self.current_info

    def visit_var(self, v: Var) -> None:
        if self.current_info is not None:
            v.info = self.current_info
        if v.type is not None:
            v.type.accept(self.type_fixer)


class TypeFixer(TypeVisitor[None]):
    def __init__(self, modules: Dict[str, MypyFile]) -> None:
        self.modules = modules

    def visit_instance(self, inst: Instance) -> None:
        # TODO: Combine Instances that are exactly the same?
        type_ref = inst.type_ref
        if type_ref is None:
            return  # We've already been here.
        del inst.type_ref
        node = lookup_qualified(self.modules, type_ref)
        if isinstance(node, TypeInfo):
            inst.type = node
            # TODO: Is this needed or redundant?
            # Also fix up the bases, just in case.
            for base in inst.type.bases:
                if base.type is None:
                    base.accept(self)
        for a in inst.args:
            a.accept(self)

    def visit_any(self, o: Any) -> None:
        pass  # Nothing to descend into.

    def visit_callable_type(self, ct: CallableType) -> None:
        if ct.fallback:
            ct.fallback.accept(self)
        for argt in ct.arg_types:
            # TODO: When is argt None?  Maybe when no type is specified?
            if argt is not None:
                argt.accept(self)
        if ct.ret_type is not None:
            ct.ret_type.accept(self)
        # TODO: What to do with ct.variables?
        for i, t in ct.bound_vars:
            t.accept(self)

    def visit_ellipsis_type(self, e: EllipsisType) -> None:
        pass  # Nothing to descend into.

    def visit_overloaded(self, t: Overloaded) -> None:
        for ct in t.items():
            ct.accept(self)

    def visit_deleted_type(self, o: Any) -> None:
        pass  # Nothing to descend into.

    def visit_none_type(self, o: Any) -> None:
        pass  # Nothing to descend into.

    def visit_partial_type(self, o: Any) -> None:
        raise RuntimeError("Shouldn't get here", o)

    def visit_tuple_type(self, tt: TupleType) -> None:
        if tt.items:
            for it in tt.items:
                it.accept(self)
        if tt.fallback is not None:
            tt.fallback.accept(self)

    def visit_type_list(self, tl: TypeList) -> None:
        for t in tl.items:
            t.accept(self)

    def visit_type_var(self, tvt: TypeVarType) -> None:
        if tvt.values:
            for vt in tvt.values:
                vt.accept(self)
        if tvt.upper_bound is not None:
            tvt.upper_bound.accept(self)

    def visit_unbound_type(self, o: UnboundType) -> None:
        for a in o.args:
            a.accept(self)

    def visit_union_type(self, ut: UnionType) -> None:
        if ut.items:
            for it in ut.items:
                it.accept(self)

    def visit_void(self, o: Any) -> None:
        pass  # Nothing to descend into.


class TypeCleaner(TypeFixer):
    counter = 0

    def visit_instance(self, inst: Instance) -> None:
        info = inst.type
        if info.alt_fullname is not None:
            return  # We've already been here
        if lookup_qualified(self.modules, info.fullname()) is not info:
            self.counter += 1
            info.alt_fullname = info.fullname() + '$' + str(self.counter)
            print("Set alt_fullname for", info.alt_fullname)
            store_qualified(self.modules, info.alt_fullname, info)
        for a in inst.args:
            a.accept(self)


class NodeCleaner(NodeFixer):
    def __init__(self, modules: Dict[str, MypyFile]) -> None:
        super().__init__(modules, TypeCleaner(modules))

    def visit_module_ref(self, value: SymbolTableNode) -> None:
        assert value.kind == MODULE_REF
        # TODO: Now what?


def lookup_qualified(modules: Dict[str, MypyFile], name: str) -> SymbolNode:
    head = name
    rest = []
    while True:
        head, tail = head.rsplit('.', 1)
        mod = modules.get(head)
        if mod is not None:
            rest.append(tail)
            break
    names = mod.names
    while True:
        if not rest:
            print('*** Cannot find', name)
            import pdb  # type: ignore
            pdb.set_trace()
            return None
        key = rest.pop()
        if key not in names:
            print('*** Cannot find', key, 'for', name)
            return None
        stnode = names[key]
        node = stnode.node
        if not rest:
            return node
        assert isinstance(node, TypeInfo)
        names = cast(TypeInfo, node).names


def store_qualified(modules: Dict[str, MypyFile], name: str, info: SymbolNode) -> None:
    print("store_qualified", name, repr(info))
    head = name
    rest = []
    while True:
        head, tail = head.rsplit('.', 1)
        mod = modules.get(head)
        if mod is not None:
            rest.append(tail)
            break
    names = mod.names
    while True:
        if not rest:
            print('*** Cannot find', name)
            import pdb  # type: ignore
            pdb.set_trace()
            return
        key = rest.pop()
        if key not in names:
            if rest:
                print('*** Cannot find', key, 'for', name)
                return
            # Store it.
            # TODO: kind might be something else?
            names[key] = SymbolTableNode(GDEF, info)
            print('Stored', names[key])
            return
        stnode = names[key]
        node = stnode.node
        if not rest:
            print('*** Overwriting!', name, stnode)
            stnode.node = info
            return
        assert isinstance(node, TypeInfo)
        names = cast(TypeInfo, node).names
    
