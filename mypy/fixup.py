"""Fix up various things after deserialization."""

from typing import Any, Dict, Optional, cast

from mypy.nodes import (MypyFile, SymbolNode, SymbolTable, SymbolTableNode,
                        TypeInfo, FuncDef, OverloadedFuncDef, Decorator, Var,
                        TypeVarExpr, ClassDef,
                        LDEF, MDEF, GDEF, MODULE_REF)
from mypy.types import (CallableType, EllipsisType, Instance, Overloaded, TupleType,
                        TypeList, TypeVarType, UnboundType, UnionType, TypeVisitor,
                        UninhabitedType, TypeType)
from mypy.visitor import NodeVisitor


def fixup_module_pass_one(tree: MypyFile, modules: Dict[str, MypyFile]) -> None:
    node_fixer = NodeFixer(modules)
    node_fixer.visit_symbol_table(tree.names)


def fixup_module_pass_two(tree: MypyFile, modules: Dict[str, MypyFile]) -> None:
    compute_all_mros(tree.names, modules)


def compute_all_mros(symtab: SymbolTable, modules: Dict[str, MypyFile]) -> None:
    for key, value in symtab.items():
        if value.kind in (LDEF, MDEF, GDEF) and isinstance(value.node, TypeInfo):
            info = value.node
            info.calculate_mro()
            assert info.mro, "No MRO calculated for %s" % (info.fullname(),)
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
            if info.defn:
                info.defn.accept(self)
            if info.names:
                self.visit_symbol_table(info.names)
            if info.subtypes:
                for st in info.subtypes:
                    self.visit_type_info(st)
            if info.bases:
                for base in info.bases:
                    base.accept(self.type_fixer)
            if info._promote:
                info._promote.accept(self.type_fixer)
            if info.tuple_type:
                info.tuple_type.accept(self.type_fixer)
        finally:
            self.current_info = save_info

    # NOTE: This method *definitely* isn't part of the NodeVisitor API.
    def visit_symbol_table(self, symtab: SymbolTable) -> None:
        # Copy the items because we may mutate symtab.
        for key, value in list(symtab.items()):
            cross_ref = value.cross_ref
            if cross_ref is not None:  # Fix up cross-reference.
                del value.cross_ref
                if cross_ref in self.modules:
                    value.node = self.modules[cross_ref]
                else:
                    stnode = lookup_qualified_stnode(self.modules, cross_ref)
                    assert stnode is not None, "Could not find cross-ref %s" % (cross_ref,)
                    value.node = stnode.node
                    value.type_override = stnode.type_override
            else:
                if isinstance(value.node, TypeInfo):
                    # TypeInfo has no accept().  TODO: Add it?
                    self.visit_type_info(value.node)
                elif value.node is not None:
                    value.node.accept(self)
                if value.type_override is not None:
                    value.type_override.accept(self.type_fixer)

    def visit_func_def(self, func: FuncDef) -> None:
        if self.current_info is not None:
            func.info = self.current_info
        if func.type is not None:
            func.type.accept(self.type_fixer)

    def visit_overloaded_func_def(self, o: OverloadedFuncDef) -> None:
        if self.current_info is not None:
            o.info = self.current_info
        if o.type:
            o.type.accept(self.type_fixer)
        for item in o.items:
            item.accept(self)

    def visit_decorator(self, d: Decorator) -> None:
        if self.current_info is not None:
            d.var.info = self.current_info
        if d.func:
            d.func.accept(self)
        if d.var:
            d.var.accept(self)
        for node in d.decorators:
            node.accept(self)

    def visit_class_def(self, c: ClassDef) -> None:
        for v in c.type_vars:
            for value in v.values:
                value.accept(self.type_fixer)
            v.upper_bound.accept(self.type_fixer)

    def visit_type_var_expr(self, tv: TypeVarExpr) -> None:
        for value in tv.values:
            value.accept(self.type_fixer)
        tv.upper_bound.accept(self.type_fixer)

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
            # argt may be None, e.g. for __self in NamedTuple constructors.
            if argt is not None:
                argt.accept(self)
        if ct.ret_type is not None:
            ct.ret_type.accept(self)
        for v in ct.variables:
            if v.values:
                for val in v.values:
                    val.accept(self)
            v.upper_bound.accept(self)

    def visit_ellipsis_type(self, e: EllipsisType) -> None:
        pass  # Nothing to descend into.

    def visit_overloaded(self, t: Overloaded) -> None:
        for ct in t.items():
            ct.accept(self)

    def visit_deleted_type(self, o: Any) -> None:
        pass  # Nothing to descend into.

    def visit_none_type(self, o: Any) -> None:
        pass  # Nothing to descend into.

    def visit_uninhabited_type(self, o: Any) -> None:
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

    def visit_type_type(self, t: TypeType) -> None:
        t.item.accept(self)


def lookup_qualified(modules: Dict[str, MypyFile], name: str) -> SymbolNode:
    stnode = lookup_qualified_stnode(modules, name)
    if stnode is None:
        return None
    else:
        return stnode.node


def lookup_qualified_stnode(modules: Dict[str, MypyFile], name: str) -> SymbolTableNode:
    head = name
    rest = []
    while True:
        assert '.' in head, "Cannot find %s" % (name,)
        head, tail = head.rsplit('.', 1)
        mod = modules.get(head)
        if mod is not None:
            rest.append(tail)
            break
    names = mod.names
    while True:
        assert rest, "Cannot find %s" % (name,)
        key = rest.pop()
        assert key in names, "Cannot find %s for %s" % (key, name)
        stnode = names[key]
        if not rest:
            return stnode
        node = stnode.node
        assert isinstance(node, TypeInfo)
        names = node.names


def store_qualified(modules: Dict[str, MypyFile], name: str, info: SymbolNode) -> None:
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
        assert rest, "Cannot find %s" % (name,)
        key = rest.pop()
        if key not in names:
            assert not rest, "Cannot find %s for %s" % (key, name)
            # Store it.
            # TODO: kind might be something else?
            names[key] = SymbolTableNode(GDEF, info)
            return
        stnode = names[key]
        node = stnode.node
        if not rest:
            stnode.node = info
            return
        assert isinstance(node, TypeInfo)
        names = node.names
