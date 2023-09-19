from __future__ import annotations

from typing import Callable

from mypy.plugin import ClassDefContext, Plugin
from mypy.plugins.common import add_attribute_to_class


class MyPlugin(Plugin):
    def get_class_decorator_hook_2(self, fullname: str) -> Callable[[ClassDefContext], bool] | None:
        if fullname == "__main__.my_decorator":
            return transform_hook
        return None


def transform_hook(ctx: ClassDefContext) -> bool:
    add_attribute_to_class(ctx.api, ctx.cls, 'magic', ctx.api.named_type('builtins.str'))
    return True


def plugin(version: str) -> type[MyPlugin]:
    return MyPlugin
