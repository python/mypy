from __future__ import annotations

from typing import Callable

from mypy.plugin import MethodContext, Plugin
from mypy.types import CallableType, Type, get_proper_type


class MethodDecoratorPlugin(Plugin):
    def get_method_hook(self, fullname: str) -> Callable[[MethodContext], Type] | None:
        if "Foo.a" in fullname:
            return method_decorator_callback
        return None


def method_decorator_callback(ctx: MethodContext) -> Type:
    default = get_proper_type(ctx.default_return_type)
    if isinstance(default, CallableType):
        str_type = ctx.api.named_generic_type("builtins.str", [])
        return default.copy_modified(ret_type=str_type)
    return ctx.default_return_type


def plugin(version: str) -> type[MethodDecoratorPlugin]:
    return MethodDecoratorPlugin
