from mypy.plugin import Plugin
from mypy.nodes import NameExpr
from mypy.types import UnionType, NoneType, Instance

class AttrPlugin(Plugin):
    def get_function_hook(self, fullname):
        if fullname.startswith('mod.Attr'):
            return attr_hook
        return None

def attr_hook(ctx):
    assert isinstance(ctx.default_return_type, Instance)
    if ctx.default_return_type.type.fullname == 'mod.Attr':
        attr_base = ctx.default_return_type
    else:
        attr_base = None
    for base in ctx.default_return_type.type.bases:
        if base.type.fullname == 'mod.Attr':
            attr_base = base
            break
    assert attr_base is not None
    last_arg_exprs = ctx.args[-1]
    if any(isinstance(expr, NameExpr) and expr.name == 'True' for expr in last_arg_exprs):
        return attr_base
    assert len(attr_base.args) == 1
    arg_type = attr_base.args[0]
    return Instance(attr_base.type, [UnionType([arg_type, NoneType()])],
                    line=ctx.default_return_type.line,
                    column=ctx.default_return_type.column)

def plugin(version):
    return AttrPlugin
