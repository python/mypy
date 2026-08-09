from __future__ import annotations

from typing import Callable

from mypy.plugin import FunctionContext, MethodContext, Plugin
from mypy.types import Type


class ArgKindsPlugin(Plugin):
    def get_function_hook(self, fullname: str) -> Callable[[FunctionContext], Type] | None:
        if "func" in fullname:
            return extract_arg_kinds_from_function
        return None

    def get_method_hook(self, fullname: str) -> Callable[[MethodContext], Type] | None:
        if "Class.method" in fullname:
            return extract_arg_kinds_from_method
        return None


def extract_arg_kinds_from_function(ctx: FunctionContext) -> Type:
    ctx.api.fail(str([[x.value for x in y] for y in ctx.arg_kinds]), ctx.context)
    return ctx.default_return_type


def extract_arg_kinds_from_method(ctx: MethodContext) -> Type:
    ctx.api.fail(str([[x.value for x in y] for y in ctx.arg_kinds]), ctx.context)
    return ctx.default_return_type


def plugin(version: str) -> type[ArgKindsPlugin]:
    return ArgKindsPlugin
