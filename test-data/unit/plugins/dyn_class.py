from mypy.plugin import Plugin
from mypy.nodes import (
    ClassDef, Block, TypeInfo, SymbolTable, SymbolTableNode, GDEF, Var
)
from mypy.types import Instance

DECL_BASES = set()

class DynPlugin(Plugin):
    def get_dynamic_class_hook(self, fullname):
        if fullname == 'mod.declarative_base':
            return add_info_hook
        return None

    def get_base_class_hook(self, fullname: str):
        if fullname in DECL_BASES:
            return replace_col_hook
        return None

def add_info_hook(ctx):
    class_def = ClassDef(ctx.name, Block([]))
    class_def.fullname = ctx.api.qualified_name(ctx.name)

    info = TypeInfo(SymbolTable(), class_def, ctx.api.cur_mod_id)
    class_def.info = info
    obj = ctx.api.builtin_type('builtins.object')
    info.mro = [info, obj.type]
    info.bases = [obj]
    ctx.api.add_symbol_table_node(ctx.name, SymbolTableNode(GDEF, info))
    DECL_BASES.add(class_def.fullname)

def replace_col_hook(ctx):
    info = ctx.cls.info
    for sym in info.names.values():
        node = sym.node
        if isinstance(node, Var) and isinstance(node.type, Instance):
            if node.type.type.fullname == 'mod.Column':
                new_sym = ctx.api.lookup_fully_qualified_or_none('mod.Instr')
                if new_sym:
                    new_info = new_sym.node
                    assert isinstance(new_info, TypeInfo)
                    node.type = Instance(new_info, node.type.args,
                                         node.type.line,
                                         node.type.column)

def plugin(version):
    return DynPlugin
