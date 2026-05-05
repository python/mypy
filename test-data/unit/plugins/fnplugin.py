from __future__ import annotations

from typing import Callable

from mypy.plugin import FunctionContext, Plugin
from mypy.types import Type


class MyPlugin(Plugin):
    def get_function_hook(self, fullname: str) -> Callable[[FunctionContext], Type] | None:
        if fullname == "__main__.f":
            return my_hook
        assert fullname is not None
        return None


def my_hook(ctx: FunctionContext) -> Type:
    return ctx.api.named_generic_type("builtins.int", [])


def plugin(version: str) -> type[MyPlugin]:
    return MyPlugin
