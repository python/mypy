from mypy.plugin import CallableType, CheckerPluginInterface, MethodSigContext, Plugin
from mypy.types import Instance, Type

class MethodSigPlugin(Plugin):
    def get_method_signature_hook(self, fullname):
        # Ensure that all names are fully qualified
        assert not fullname.endswith(' of Foo')

        if fullname.startswith('__main__.Foo.'):
            return my_hook

        return None

def _str_to_int(api: CheckerPluginInterface, typ: Type) -> Type:
    if isinstance(typ, Instance):
        if typ.type.fullname == 'builtins.str':
            return api.named_generic_type('builtins.int', [])
        elif typ.args:
            return typ.copy_modified(args=[_str_to_int(api, t) for t in typ.args])

    return typ

def my_hook(ctx: MethodSigContext) -> CallableType:
    return ctx.default_signature.copy_modified(
        arg_types=[_str_to_int(ctx.api, t) for t in ctx.default_signature.arg_types],
        ret_type=_str_to_int(ctx.api, ctx.default_signature.ret_type),
    )

def plugin(version):
    return MethodSigPlugin
