from __future__ import annotations

from typing import Callable

from mypy.plugin import FunctionContext, Plugin
from mypy.types import Type


class Plugin2(Plugin):
    def get_function_hook(self, fullname: str) -> Callable[[FunctionContext], Type] | None:
        if fullname in ("__main__.f", "__main__.g"):
            return str_hook
        return None


def str_hook(ctx: FunctionContext) -> Type:
    return ctx.api.named_generic_type("builtins.str", [])


def plugin(version: str) -> type[Plugin2]:
    return Plugin2
