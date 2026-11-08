from __future__ import annotations

from typing import Callable

from mypy.nodes import (
    GDEF,
    Block,
    ClassDef,
    IndexExpr,
    MemberExpr,
    NameExpr,
    PlaceholderNode,
    RefExpr,
    SymbolTable,
    SymbolTableNode,
    TypeApplication,
    TypeInfo,
)
from mypy.plugin import DynamicClassDefContext, Plugin
from mypy.types import Instance


class DynPlugin(Plugin):
    def get_dynamic_class_hook(
        self, fullname: str
    ) -> Callable[[DynamicClassDefContext], None] | None:
        if "from_queryset" in fullname:
            return add_info_hook
        if "as_manager" in fullname:
            return as_manager_hook
        return None


def add_info_hook(ctx: DynamicClassDefContext) -> None:
    # Defer until the imported queryset has been fully analysed.
    fullname = ctx.api.qualified_name(ctx.name)
    existing = ctx.api.lookup_fully_qualified_or_none(fullname)
    if existing is not None and isinstance(existing.node, TypeInfo):
        return
    assert isinstance(ctx.call.args[0], RefExpr)
    queryset_fullname = ctx.call.args[0].fullname
    symbol = (
        ctx.api.lookup_fully_qualified_or_none(queryset_fullname)
        if queryset_fullname
        else None
    )
    if symbol is None or not isinstance(symbol.node, TypeInfo) or not symbol.node.mro:
        assert not ctx.api.final_iteration
        if existing is None or not isinstance(existing.node, PlaceholderNode):
            placeholder = PlaceholderNode(fullname, ctx.call, ctx.call.line, becomes_typeinfo=True)
            ctx.api.add_symbol_table_node(ctx.name, SymbolTableNode(GDEF, placeholder))
        ctx.api.defer()
        return
    queryset_info = symbol.node
    class_def = ClassDef(ctx.name, Block([]))
    class_def.fullname = fullname
    info = TypeInfo(SymbolTable(), class_def, ctx.api.cur_mod_id)
    class_def.info = info
    info.mro = [info, *queryset_info.mro]
    info.bases = [Instance(queryset_info, [])]
    ctx.api.add_symbol_table_node(ctx.name, SymbolTableNode(GDEF, info))

def as_manager_hook(ctx: DynamicClassDefContext) -> None:
    class_def = ClassDef(ctx.name, Block([]))
    class_def.fullname = ctx.api.qualified_name(ctx.name)

    info = TypeInfo(SymbolTable(), class_def, ctx.api.cur_mod_id)
    class_def.info = info
    assert isinstance(ctx.call.callee, MemberExpr)
    assert isinstance(ctx.call.callee.expr, IndexExpr)
    assert isinstance(ctx.call.callee.expr.analyzed, TypeApplication)
    assert isinstance(ctx.call.callee.expr.analyzed.expr, NameExpr)

    queryset_type_fullname = ctx.call.callee.expr.analyzed.expr.fullname
    queryset_node = ctx.api.lookup_fully_qualified_or_none(queryset_type_fullname)
    assert queryset_node is not None
    queryset_info = queryset_node.node
    assert isinstance(queryset_info, TypeInfo)
    parameter_type = ctx.call.callee.expr.analyzed.types[0]

    obj = ctx.api.named_type("builtins.object")
    info.mro = [info, queryset_info, obj.type]
    info.bases = [Instance(queryset_info, [parameter_type])]
    ctx.api.add_symbol_table_node(ctx.name, SymbolTableNode(GDEF, info))


def plugin(version: str) -> type[DynPlugin]:
    return DynPlugin
