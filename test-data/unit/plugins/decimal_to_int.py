from __future__ import annotations

from typing import Callable

from mypy.plugin import AnalyzeTypeContext, Plugin
from mypy.types import Type


class MyPlugin(Plugin):
    def get_type_analyze_hook(self, fullname: str) -> Callable[[AnalyzeTypeContext], Type] | None:
        if fullname in ("decimal.Decimal", "_decimal.Decimal"):
            return decimal_to_int_hook
        return None


def decimal_to_int_hook(ctx: AnalyzeTypeContext) -> Type:
    return ctx.api.named_type("builtins.int", [])


def plugin(version: str) -> type[MyPlugin]:
    return MyPlugin
