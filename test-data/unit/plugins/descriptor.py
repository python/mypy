from __future__ import annotations

from typing import Callable

from mypy.plugin import MethodContext, MethodSigContext, Plugin
from mypy.types import CallableType, NoneType, Type, get_proper_type


class DescriptorPlugin(Plugin):
    def get_method_hook(self, fullname: str) -> Callable[[MethodContext], Type] | None:
        if fullname == "__main__.Desc.__get__":
            return get_hook
        return None

    def get_method_signature_hook(
        self, fullname: str
    ) -> Callable[[MethodSigContext], CallableType] | None:
        if fullname == "__main__.Desc.__set__":
            return set_hook
        return None


def get_hook(ctx: MethodContext) -> Type:
    arg = get_proper_type(ctx.arg_types[0][0])
    if isinstance(arg, NoneType):
        return ctx.api.named_generic_type("builtins.str", [])
    return ctx.api.named_generic_type("builtins.int", [])


def set_hook(ctx: MethodSigContext) -> CallableType:
    return CallableType(
        [
            ctx.api.named_generic_type("__main__.Cls", []),
            ctx.api.named_generic_type("builtins.int", []),
        ],
        ctx.default_signature.arg_kinds,
        ctx.default_signature.arg_names,
        ctx.default_signature.ret_type,
        ctx.default_signature.fallback,
    )


def plugin(version: str) -> type[DescriptorPlugin]:
    return DescriptorPlugin
