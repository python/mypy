from __future__ import annotations

from typing import Callable

from mypy.nodes import GDEF, MDEF, Block, ClassDef, SymbolTable, SymbolTableNode, TypeInfo, Var
from mypy.plugin import ClassDefContext, DynamicClassDefContext, Plugin


class DynPlugin(Plugin):
    def get_dynamic_class_hook(
        self, fullname: str
    ) -> Callable[[DynamicClassDefContext], None] | None:
        if fullname == "lib.declarative_base":
            return add_info_hook
        return None

    def get_base_class_hook(self, fullname: str) -> Callable[[ClassDefContext], None] | None:
        sym = self.lookup_fully_qualified(fullname)
        if sym and isinstance(sym.node, TypeInfo):
            if sym.node.metadata.get("magic"):
                return add_magic_hook
        return None


def add_info_hook(ctx: DynamicClassDefContext) -> None:
    class_def = ClassDef(ctx.name, Block([]))
    class_def.fullname = ctx.api.qualified_name(ctx.name)

    info = TypeInfo(SymbolTable(), class_def, ctx.api.cur_mod_id)
    class_def.info = info
    obj = ctx.api.named_type("builtins.object", [])
    info.mro = [info, obj.type]
    info.bases = [obj]
    ctx.api.add_symbol_table_node(ctx.name, SymbolTableNode(GDEF, info))
    info.metadata["magic"] = {"value": True}


def add_magic_hook(ctx: ClassDefContext) -> None:
    info = ctx.cls.info
    str_type = ctx.api.named_type_or_none("builtins.str", [])
    assert str_type is not None
    var = Var("__magic__", str_type)
    var.info = info
    info.names["__magic__"] = SymbolTableNode(MDEF, var)


def plugin(version: str) -> type[DynPlugin]:
    return DynPlugin
