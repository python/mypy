from mypy.plugin import (
    CallableType, CheckerPluginInterface, MethodSigContext, MethodContext, Plugin
)
from mypy.types import Instance, Type


class MethodPlugin(Plugin):
    def get_method_signature_hook(self, fullname):
        if fullname.startswith('__main__.Foo.'):
            return my_meth_sig_hook
        return None

    def get_method_hook(self, fullname):
        if fullname.startswith('__main__.Bar.'):
            return my_meth_hook
        return None


def _str_to_int(api: CheckerPluginInterface, typ: Type) -> Type:
    if isinstance(typ, Instance):
        if typ.type.fullname == 'builtins.str':
            return api.named_generic_type('builtins.int', [])
        elif typ.args:
            return typ.copy_modified(args=[_str_to_int(api, t) for t in typ.args])
    return typ


def _float_to_int(api: CheckerPluginInterface, typ: Type) -> Type:
    if isinstance(typ, Instance):
        if typ.type.fullname == 'builtins.float':
            return api.named_generic_type('builtins.int', [])
        elif typ.args:
            return typ.copy_modified(args=[_float_to_int(api, t) for t in typ.args])
    return typ


def my_meth_sig_hook(ctx: MethodSigContext) -> CallableType:
    return ctx.default_signature.copy_modified(
        arg_types=[_str_to_int(ctx.api, t) for t in ctx.default_signature.arg_types],
        ret_type=_str_to_int(ctx.api, ctx.default_signature.ret_type),
    )


def my_meth_hook(ctx: MethodContext) -> Type:
    return _float_to_int(ctx.api, ctx.default_return_type)


def plugin(version):
    return MethodPlugin
