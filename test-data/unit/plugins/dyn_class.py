from __future__ import annotations

from typing import Callable

from mypy.nodes import GDEF, Block, ClassDef, SymbolTable, SymbolTableNode, TypeInfo, Var
from mypy.plugin import ClassDefContext, DynamicClassDefContext, Plugin
from mypy.types import Instance, get_proper_type

DECL_BASES = set()


class DynPlugin(Plugin):
    def get_dynamic_class_hook(
        self, fullname: str
    ) -> Callable[[DynamicClassDefContext], None] | None:
        if fullname == "mod.declarative_base":
            return add_info_hook
        return None

    def get_base_class_hook(self, fullname: str) -> Callable[[ClassDefContext], None] | None:
        if fullname in DECL_BASES:
            return replace_col_hook
        return None


def add_info_hook(ctx: DynamicClassDefContext) -> None:
    class_def = ClassDef(ctx.name, Block([]))
    class_def.fullname = ctx.api.qualified_name(ctx.name)

    info = TypeInfo(SymbolTable(), class_def, ctx.api.cur_mod_id)
    class_def.info = info
    obj = ctx.api.named_type("builtins.object")
    info.mro = [info, obj.type]
    info.bases = [obj]
    ctx.api.add_symbol_table_node(ctx.name, SymbolTableNode(GDEF, info))
    DECL_BASES.add(class_def.fullname)


def replace_col_hook(ctx: ClassDefContext) -> None:
    info = ctx.cls.info
    for sym in info.names.values():
        node = sym.node
        if isinstance(node, Var) and isinstance(
            (node_type := get_proper_type(node.type)), Instance
        ):
            if node_type.type.fullname == "mod.Column":
                new_sym = ctx.api.lookup_fully_qualified_or_none("mod.Instr")
                if new_sym:
                    new_info = new_sym.node
                    assert isinstance(new_info, TypeInfo)
                    node.type = Instance(
                        new_info, node_type.args, node_type.line, node_type.column
                    )


def plugin(version: str) -> type[DynPlugin]:
    return DynPlugin
