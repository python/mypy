from mypy.plugin import Plugin
from mypy.types import NoneType, CallableType


class DescriptorPlugin(Plugin):
    def get_method_hook(self, fullname):
        if fullname == "__main__.Desc.__get__":
            return get_hook
        return None

    def get_method_signature_hook(self, fullname):
        if fullname == "__main__.Desc.__set__":
            return set_hook
        return None


def get_hook(ctx):
    if isinstance(ctx.arg_types[0][0], NoneType):
        return ctx.api.named_type("builtins.str")
    return ctx.api.named_type("builtins.int")


def set_hook(ctx):
    return CallableType(
        [ctx.api.named_type("__main__.Cls"), ctx.api.named_type("builtins.int")],
        ctx.default_signature.arg_kinds,
        ctx.default_signature.arg_names,
        ctx.default_signature.ret_type,
        ctx.default_signature.fallback,
    )


def plugin(version):
    return DescriptorPlugin
