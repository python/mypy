from mypy.plugin import Plugin
from mypy.nodes import (
    ClassDef, Block, TypeInfo, SymbolTable, SymbolTableNode, MDEF, GDEF, Var
)


class DynPlugin(Plugin):
    def get_dynamic_class_hook(self, fullname):
        if fullname == 'lib.declarative_base':
            return add_info_hook
        return None

    def get_base_class_hook(self, fullname: str):
        sym = self.lookup_fully_qualified(fullname)
        if sym and isinstance(sym.node, TypeInfo):
            if sym.node.metadata.get('magic'):
                return add_magic_hook
        return None


def add_info_hook(ctx) -> None:
    class_def = ClassDef(ctx.name, Block([]))
    class_def.fullname = ctx.api.qualified_name(ctx.name)

    info = TypeInfo(SymbolTable(), class_def, ctx.api.cur_mod_id)
    class_def.info = info
    obj = ctx.api.builtin_type('builtins.object')
    info.mro = [info, obj.type]
    info.bases = [obj]
    ctx.api.add_symbol_table_node(ctx.name, SymbolTableNode(GDEF, info))
    info.metadata['magic'] = True


def add_magic_hook(ctx) -> None:
    info = ctx.cls.info
    str_type = ctx.api.named_type_or_none('builtins.str', [])
    assert str_type is not None
    var = Var('__magic__', str_type)
    var.info = info
    info.names['__magic__'] = SymbolTableNode(MDEF, var)


def plugin(version):
    return DynPlugin
