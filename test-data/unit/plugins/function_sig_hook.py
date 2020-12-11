from mypy.plugin import CallableType, CheckerPluginInterface, FunctionSigContext, Plugin
from mypy.types import Instance, Type

class FunctionSigPlugin(Plugin):
    def get_function_signature_hook(self, fullname):
        if fullname == '__main__.dynamic_signature':
            return my_hook
        return None

def _str_to_int(api: CheckerPluginInterface, typ: Type) -> Type:
    if isinstance(typ, Instance):
        if typ.type.fullname == 'builtins.str':
            return api.named_generic_type('builtins.int', [])
        elif typ.args:
            return typ.copy_modified(args=[_str_to_int(api, t) for t in typ.args])

    return typ

def my_hook(ctx: FunctionSigContext) -> CallableType:
    return ctx.default_signature.copy_modified(
        arg_types=[_str_to_int(ctx.api, t) for t in ctx.default_signature.arg_types],
        ret_type=_str_to_int(ctx.api, ctx.default_signature.ret_type),
    )

def plugin(version):
    return FunctionSigPlugin
