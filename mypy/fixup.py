"""Fix up various things after deserialization."""

from typing import Any, Dict, Optional

from mypy.nodes import (
    MypyFile, SymbolNode, SymbolTable, SymbolTableNode,
    TypeInfo, FuncDef, OverloadedFuncDef, Decorator, Var,
    TypeVarExpr, ClassDef, Block, TypeAlias,
)
from mypy.types import (
    CallableType, Instance, Overloaded, TupleType, TypedDictType,
    TypeVarType, UnboundType, UnionType, TypeVisitor, LiteralType,
    TypeType, NOT_READY
)
from mypy.visitor import NodeVisitor
from mypy.lookup import lookup_fully_qualified


# N.B: we do a quick_and_dirty fixup in both quick_and_dirty mode and
# when fixing up a fine-grained incremental cache load (since there may
# be cross-refs into deleted modules)
def fixup_module(tree: MypyFile, modules: Dict[str, MypyFile],
                 quick_and_dirty: bool) -> None:
    node_fixer = NodeFixer(modules, quick_and_dirty)
    node_fixer.visit_symbol_table(tree.names)


# TODO: Fix up .info when deserializing, i.e. much earlier.
class NodeFixer(NodeVisitor[None]):
    current_info = None  # type: Optional[TypeInfo]

    def __init__(self, modules: Dict[str, MypyFile], quick_and_dirty: bool) -> None:
        self.modules = modules
        self.quick_and_dirty = quick_and_dirty
        self.type_fixer = TypeFixer(self.modules, quick_and_dirty)

    # NOTE: This method isn't (yet) part of the NodeVisitor API.
    def visit_type_info(self, info: TypeInfo) -> None:
        save_info = self.current_info
        try:
            self.current_info = info
            if info.defn:
                info.defn.accept(self)
            if info.names:
                self.visit_symbol_table(info.names)
            if info.bases:
                for base in info.bases:
                    base.accept(self.type_fixer)
            if info._promote:
                info._promote.accept(self.type_fixer)
            if info.tuple_type:
                info.tuple_type.accept(self.type_fixer)
            if info.typeddict_type:
                info.typeddict_type.accept(self.type_fixer)
            if info.declared_metaclass:
                info.declared_metaclass.accept(self.type_fixer)
            if info.metaclass_type:
                info.metaclass_type.accept(self.type_fixer)
            if info._mro_refs:
                info.mro = [lookup_qualified_typeinfo(self.modules, name, self.quick_and_dirty)
                            for name in info._mro_refs]
                info._mro_refs = None
        finally:
            self.current_info = save_info

    # NOTE: This method *definitely* isn't part of the NodeVisitor API.
    def visit_symbol_table(self, symtab: SymbolTable) -> None:
        # Copy the items because we may mutate symtab.
        for key, value in list(symtab.items()):
            cross_ref = value.cross_ref
            if cross_ref is not None:  # Fix up cross-reference.
                value.cross_ref = None
                if cross_ref in self.modules:
                    value.node = self.modules[cross_ref]
                else:
                    stnode = lookup_qualified_stnode(self.modules, cross_ref,
                                                     self.quick_and_dirty)
                    if stnode is not None:
                        value.node = stnode.node
                    elif not self.quick_and_dirty:
                        assert stnode is not None, "Could not find cross-ref %s" % (cross_ref,)
                    else:
                        # We have a missing crossref in quick mode, need to put something
                        value.node = stale_info(self.modules)
            else:
                if isinstance(value.node, TypeInfo):
                    # TypeInfo has no accept().  TODO: Add it?
                    self.visit_type_info(value.node)
                elif value.node is not None:
                    value.node.accept(self)

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
        if o.impl:
            o.impl.accept(self)

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

    def visit_type_alias(self, a: TypeAlias) -> None:
        a.target.accept(self.type_fixer)


class TypeFixer(TypeVisitor[None]):
    def __init__(self, modules: Dict[str, MypyFile], quick_and_dirty: bool) -> None:
        self.modules = modules
        self.quick_and_dirty = quick_and_dirty

    def visit_instance(self, inst: Instance) -> None:
        # TODO: Combine Instances that are exactly the same?
        type_ref = inst.type_ref
        if type_ref is None:
            return  # We've already been here.
        inst.type_ref = None
        inst.type = lookup_qualified_typeinfo(self.modules, type_ref, self.quick_and_dirty)
        # TODO: Is this needed or redundant?
        # Also fix up the bases, just in case.
        for base in inst.type.bases:
            if base.type is NOT_READY:
                base.accept(self)
        for a in inst.args:
            a.accept(self)
        if inst.final_value is not None:
            inst.final_value.accept(self)

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
        for arg in ct.bound_args:
            if arg:
                arg.accept(self)

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

    def visit_typeddict_type(self, tdt: TypedDictType) -> None:
        if tdt.items:
            for it in tdt.items.values():
                it.accept(self)
        if tdt.fallback is not None:
            tdt.fallback.accept(self)

    def visit_literal_type(self, lt: LiteralType) -> None:
        lt.fallback.accept(self)

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


def lookup_qualified_typeinfo(modules: Dict[str, MypyFile], name: str,
                              quick_and_dirty: bool) -> TypeInfo:
    node = lookup_qualified(modules, name, quick_and_dirty)
    if isinstance(node, TypeInfo):
        return node
    else:
        # Looks like a missing TypeInfo in quick mode, put something there
        assert quick_and_dirty, "Should never get here in normal mode," \
                                " got {}:{} instead of TypeInfo".format(type(node).__name__,
                                                                        node.fullname() if node
                                                                        else '')
        return stale_info(modules)


def lookup_qualified(modules: Dict[str, MypyFile], name: str,
                     quick_and_dirty: bool) -> Optional[SymbolNode]:
    stnode = lookup_qualified_stnode(modules, name, quick_and_dirty)
    if stnode is None:
        return None
    else:
        return stnode.node


def lookup_qualified_stnode(modules: Dict[str, MypyFile], name: str,
                            quick_and_dirty: bool) -> Optional[SymbolTableNode]:
    return lookup_fully_qualified(name, modules, raise_on_missing=not quick_and_dirty)


def stale_info(modules: Dict[str, MypyFile]) -> TypeInfo:
    suggestion = "<stale cache: consider running mypy without --quick>"
    dummy_def = ClassDef(suggestion, Block([]))
    dummy_def.fullname = suggestion

    info = TypeInfo(SymbolTable(), dummy_def, "<stale>")
    obj_type = lookup_qualified(modules, 'builtins.object', False)
    assert isinstance(obj_type, TypeInfo)
    info.bases = [Instance(obj_type, [])]
    info.mro = [info, obj_type]
    return info
