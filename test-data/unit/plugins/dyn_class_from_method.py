from mypy.nodes import (Block, ClassDef, GDEF, SymbolTable, SymbolTableNode, TypeInfo)
from mypy.plugin import DynamicClassDefContext, Plugin
from mypy.types import Instance


class DynPlugin(Plugin):
    def get_dynamic_class_hook(self, fullname):
        if 'from_queryset' in fullname:
            return add_info_hook
        return None


def add_info_hook(ctx: DynamicClassDefContext):
    class_def = ClassDef(ctx.name, Block([]))
    class_def.fullname = ctx.api.qualified_name(ctx.name)

    info = TypeInfo(SymbolTable(), class_def, ctx.api.cur_mod_id)
    class_def.info = info
    queryset_type_fullname = ctx.call.args[0].fullname
    queryset_info = ctx.api.lookup_fully_qualified_or_none(queryset_type_fullname).node  # type: TypeInfo
    obj = ctx.api.builtin_type('builtins.object')
    info.mro = [info, queryset_info, obj.type]
    info.bases = [Instance(queryset_info, [])]
    ctx.api.add_symbol_table_node(ctx.name, SymbolTableNode(GDEF, info))


def plugin(version):
    return DynPlugin
