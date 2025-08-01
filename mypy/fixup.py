"""Fix up various things after deserialization."""

from __future__ import annotations

from typing import Any, Final

from mypy.lookup import lookup_fully_qualified
from mypy.nodes import (
    Block,
    ClassDef,
    Decorator,
    FuncDef,
    MypyFile,
    OverloadedFuncDef,
    ParamSpecExpr,
    SymbolTable,
    TypeAlias,
    TypeInfo,
    TypeVarExpr,
    TypeVarTupleExpr,
    Var,
)
from mypy.types import (
    NOT_READY,
    AnyType,
    CallableType,
    Instance,
    LiteralType,
    Overloaded,
    Parameters,
    ParamSpecType,
    TupleType,
    TypeAliasType,
    TypedDictType,
    TypeOfAny,
    TypeType,
    TypeVarTupleType,
    TypeVarType,
    TypeVisitor,
    UnboundType,
    UnionType,
    UnpackType,
)
from mypy.visitor import NodeVisitor


# N.B: we do a allow_missing fixup when fixing up a fine-grained
# incremental cache load (since there may be cross-refs into deleted
# modules)
def fixup_module(tree: MypyFile, modules: dict[str, MypyFile], allow_missing: bool) -> None:
    node_fixer = NodeFixer(modules, allow_missing)
    node_fixer.visit_symbol_table(tree.names, tree.fullname)


# TODO: Fix up .info when deserializing, i.e. much earlier.
class NodeFixer(NodeVisitor[None]):
    current_info: TypeInfo | None = None

    def __init__(self, modules: dict[str, MypyFile], allow_missing: bool) -> None:
        self.modules = modules
        self.allow_missing = allow_missing
        self.type_fixer = TypeFixer(self.modules, allow_missing)

    # NOTE: This method isn't (yet) part of the NodeVisitor API.
    def visit_type_info(self, info: TypeInfo) -> None:
        save_info = self.current_info
        try:
            self.current_info = info
            if info.defn:
                info.defn.accept(self)
            if info.names:
                self.visit_symbol_table(info.names, info.fullname)
            if info.bases:
                for base in info.bases:
                    base.accept(self.type_fixer)
            if info._promote:
                for p in info._promote:
                    p.accept(self.type_fixer)
            if info.tuple_type:
                info.tuple_type.accept(self.type_fixer)
                info.update_tuple_type(info.tuple_type)
                if info.special_alias:
                    info.special_alias.alias_tvars = list(info.defn.type_vars)
                    for i, t in enumerate(info.defn.type_vars):
                        if isinstance(t, TypeVarTupleType):
                            info.special_alias.tvar_tuple_index = i
            if info.typeddict_type:
                info.typeddict_type.accept(self.type_fixer)
                info.update_typeddict_type(info.typeddict_type)
                if info.special_alias:
                    info.special_alias.alias_tvars = list(info.defn.type_vars)
                    for i, t in enumerate(info.defn.type_vars):
                        if isinstance(t, TypeVarTupleType):
                            info.special_alias.tvar_tuple_index = i
            if info.declared_metaclass:
                info.declared_metaclass.accept(self.type_fixer)
            if info.metaclass_type:
                info.metaclass_type.accept(self.type_fixer)
            if info.alt_promote:
                info.alt_promote.accept(self.type_fixer)
                instance = Instance(info, [])
                # Hack: We may also need to add a backwards promotion (from int to native int),
                # since it might not be serialized.
                if instance not in info.alt_promote.type._promote:
                    info.alt_promote.type._promote.append(instance)
            if info._mro_refs:
                info.mro = [
                    lookup_fully_qualified_typeinfo(
                        self.modules, name, allow_missing=self.allow_missing
                    )
                    for name in info._mro_refs
                ]
                info._mro_refs = None
        finally:
            self.current_info = save_info

    # NOTE: This method *definitely* isn't part of the NodeVisitor API.
    def visit_symbol_table(self, symtab: SymbolTable, table_fullname: str) -> None:
        # Copy the items because we may mutate symtab.
        for key in list(symtab):
            value = symtab[key]
            cross_ref = value.cross_ref
            if cross_ref is not None:  # Fix up cross-reference.
                value.cross_ref = None
                if cross_ref in self.modules:
                    value.node = self.modules[cross_ref]
                else:
                    stnode = lookup_fully_qualified(
                        cross_ref, self.modules, raise_on_missing=not self.allow_missing
                    )
                    if stnode is not None:
                        if stnode is value:
                            # The node seems to refer to itself, which can mean that
                            # the target is a deleted submodule of the current module,
                            # and thus lookup falls back to the symbol table of the parent
                            # package. Here's how this may happen:
                            #
                            #   pkg/__init__.py:
                            #     from pkg import sub
                            #
                            # Now if pkg.sub is deleted, the pkg.sub symbol table entry
                            # appears to refer to itself. Replace the entry with a
                            # placeholder to avoid a crash. We can't delete the entry,
                            # as it would stop dependency propagation.
                            value.node = Var(key + "@deleted")
                        else:
                            assert stnode.node is not None, (table_fullname + "." + key, cross_ref)
                            value.node = stnode.node
                    elif not self.allow_missing:
                        assert False, f"Could not find cross-ref {cross_ref}"
                    else:
                        # We have a missing crossref in allow missing mode, need to put something
                        value.node = missing_info(self.modules)
            else:
                if isinstance(value.node, TypeInfo):
                    # TypeInfo has no accept().  TODO: Add it?
                    self.visit_type_info(value.node)
                elif value.node is not None:
                    value.node.accept(self)
                else:
                    assert False, f"Unexpected empty node {key!r}: {value}"

    def visit_func_def(self, func: FuncDef) -> None:
        if self.current_info is not None:
            func.info = self.current_info
        if func.type is not None:
            func.type.accept(self.type_fixer)
            if isinstance(func.type, CallableType):
                func.type.definition = func

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
            v.accept(self.type_fixer)

    def visit_type_var_expr(self, tv: TypeVarExpr) -> None:
        for value in tv.values:
            value.accept(self.type_fixer)
        tv.upper_bound.accept(self.type_fixer)
        tv.default.accept(self.type_fixer)

    def visit_paramspec_expr(self, p: ParamSpecExpr) -> None:
        p.upper_bound.accept(self.type_fixer)
        p.default.accept(self.type_fixer)

    def visit_type_var_tuple_expr(self, tv: TypeVarTupleExpr) -> None:
        tv.upper_bound.accept(self.type_fixer)
        tv.tuple_fallback.accept(self.type_fixer)
        tv.default.accept(self.type_fixer)

    def visit_var(self, v: Var) -> None:
        if self.current_info is not None:
            v.info = self.current_info
        if v.type is not None:
            v.type.accept(self.type_fixer)
        if v.setter_type is not None:
            v.setter_type.accept(self.type_fixer)

    def visit_type_alias(self, a: TypeAlias) -> None:
        a.target.accept(self.type_fixer)
        for v in a.alias_tvars:
            v.accept(self.type_fixer)


class TypeFixer(TypeVisitor[None]):
    def __init__(self, modules: dict[str, MypyFile], allow_missing: bool) -> None:
        self.modules = modules
        self.allow_missing = allow_missing

    def visit_instance(self, inst: Instance) -> None:
        # TODO: Combine Instances that are exactly the same?
        type_ref = inst.type_ref
        if type_ref is None:
            return  # We've already been here.
        inst.type_ref = None
        inst.type = lookup_fully_qualified_typeinfo(
            self.modules, type_ref, allow_missing=self.allow_missing
        )
        # TODO: Is this needed or redundant?
        # Also fix up the bases, just in case.
        for base in inst.type.bases:
            if base.type is NOT_READY:
                base.accept(self)
        for a in inst.args:
            a.accept(self)
        if inst.last_known_value is not None:
            inst.last_known_value.accept(self)
        if inst.extra_attrs:
            for v in inst.extra_attrs.attrs.values():
                v.accept(self)

    def visit_type_alias_type(self, t: TypeAliasType) -> None:
        type_ref = t.type_ref
        if type_ref is None:
            return  # We've already been here.
        t.type_ref = None
        t.alias = lookup_fully_qualified_alias(
            self.modules, type_ref, allow_missing=self.allow_missing
        )
        for a in t.args:
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
            v.accept(self)
        if ct.type_guard is not None:
            ct.type_guard.accept(self)
        if ct.type_is is not None:
            ct.type_is.accept(self)

    def visit_overloaded(self, t: Overloaded) -> None:
        for ct in t.items:
            ct.accept(self)

    def visit_erased_type(self, o: Any) -> None:
        # This type should exist only temporarily during type inference
        raise RuntimeError("Shouldn't get here", o)

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
        if tt.partial_fallback is not None:
            tt.partial_fallback.accept(self)

    def visit_typeddict_type(self, tdt: TypedDictType) -> None:
        if tdt.items:
            for it in tdt.items.values():
                it.accept(self)
        if tdt.fallback is not None:
            if tdt.fallback.type_ref is not None:
                if (
                    lookup_fully_qualified(
                        tdt.fallback.type_ref,
                        self.modules,
                        raise_on_missing=not self.allow_missing,
                    )
                    is None
                ):
                    # We reject fake TypeInfos for TypedDict fallbacks because
                    # the latter are used in type checking and must be valid.
                    tdt.fallback.type_ref = "typing._TypedDict"
            tdt.fallback.accept(self)

    def visit_literal_type(self, lt: LiteralType) -> None:
        lt.fallback.accept(self)

    def visit_type_var(self, tvt: TypeVarType) -> None:
        if tvt.values:
            for vt in tvt.values:
                vt.accept(self)
        tvt.upper_bound.accept(self)
        tvt.default.accept(self)

    def visit_param_spec(self, p: ParamSpecType) -> None:
        p.upper_bound.accept(self)
        p.default.accept(self)

    def visit_type_var_tuple(self, t: TypeVarTupleType) -> None:
        t.tuple_fallback.accept(self)
        t.upper_bound.accept(self)
        t.default.accept(self)

    def visit_unpack_type(self, u: UnpackType) -> None:
        u.type.accept(self)

    def visit_parameters(self, p: Parameters) -> None:
        for argt in p.arg_types:
            if argt is not None:
                argt.accept(self)
        for var in p.variables:
            var.accept(self)

    def visit_unbound_type(self, o: UnboundType) -> None:
        for a in o.args:
            a.accept(self)

    def visit_union_type(self, ut: UnionType) -> None:
        if ut.items:
            for it in ut.items:
                it.accept(self)

    def visit_type_type(self, t: TypeType) -> None:
        t.item.accept(self)


def lookup_fully_qualified_typeinfo(
    modules: dict[str, MypyFile], name: str, *, allow_missing: bool
) -> TypeInfo:
    stnode = lookup_fully_qualified(name, modules, raise_on_missing=not allow_missing)
    node = stnode.node if stnode else None
    if isinstance(node, TypeInfo):
        return node
    else:
        # Looks like a missing TypeInfo during an initial daemon load, put something there
        assert (
            allow_missing
        ), "Should never get here in normal mode, got {}:{} instead of TypeInfo".format(
            type(node).__name__, node.fullname if node else ""
        )
        return missing_info(modules)


def lookup_fully_qualified_alias(
    modules: dict[str, MypyFile], name: str, *, allow_missing: bool
) -> TypeAlias:
    stnode = lookup_fully_qualified(name, modules, raise_on_missing=not allow_missing)
    node = stnode.node if stnode else None
    if isinstance(node, TypeAlias):
        return node
    elif isinstance(node, TypeInfo):
        if node.special_alias:
            # Already fixed up.
            return node.special_alias
        if node.tuple_type:
            alias = TypeAlias.from_tuple_type(node)
        elif node.typeddict_type:
            alias = TypeAlias.from_typeddict_type(node)
        else:
            assert allow_missing
            return missing_alias()
        node.special_alias = alias
        return alias
    else:
        # Looks like a missing TypeAlias during an initial daemon load, put something there
        assert (
            allow_missing
        ), "Should never get here in normal mode, got {}:{} instead of TypeAlias".format(
            type(node).__name__, node.fullname if node else ""
        )
        return missing_alias()


_SUGGESTION: Final = "<missing {}: *should* have gone away during fine-grained update>"


def missing_info(modules: dict[str, MypyFile]) -> TypeInfo:
    suggestion = _SUGGESTION.format("info")
    dummy_def = ClassDef(suggestion, Block([]))
    dummy_def.fullname = suggestion

    info = TypeInfo(SymbolTable(), dummy_def, "<missing>")
    obj_type = lookup_fully_qualified_typeinfo(modules, "builtins.object", allow_missing=False)
    info.bases = [Instance(obj_type, [])]
    info.mro = [info, obj_type]
    return info


def missing_alias() -> TypeAlias:
    suggestion = _SUGGESTION.format("alias")
    return TypeAlias(AnyType(TypeOfAny.special_form), suggestion, line=-1, column=-1)
