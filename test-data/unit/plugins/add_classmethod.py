from __future__ import annotations

from typing import Callable

from mypy.nodes import ARG_POS, Argument, Var
from mypy.plugin import ClassDefContext, Plugin
from mypy.plugins.common import add_method
from mypy.types import NoneType


class ClassMethodPlugin(Plugin):
    def get_base_class_hook(self, fullname: str) -> Callable[[ClassDefContext], None] | None:
        if "BaseAddMethod" in fullname:
            return add_extra_methods_hook
        return None


def add_extra_methods_hook(ctx: ClassDefContext) -> None:
    add_method(ctx, "foo_classmethod", [], NoneType(), is_classmethod=True)
    add_method(
        ctx,
        "foo_staticmethod",
        [Argument(Var(""), ctx.api.named_type("builtins.int"), None, ARG_POS)],
        ctx.api.named_type("builtins.str"),
        is_staticmethod=True,
    )


def plugin(version: str) -> type[ClassMethodPlugin]:
    return ClassMethodPlugin
