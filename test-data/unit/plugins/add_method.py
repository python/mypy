from __future__ import annotations

from typing import Callable

from mypy.plugin import ClassDefContext, Plugin
from mypy.plugins.common import add_method
from mypy.types import NoneType


class AddOverrideMethodPlugin(Plugin):
    def get_base_class_hook(self, fullname: str) -> Callable[[ClassDefContext], None] | None:
        if "WithFoo" in fullname:
            return add_extra_methods_hook
        return None


def add_extra_methods_hook(ctx: ClassDefContext) -> None:
    add_method(ctx, "foo1", [], NoneType())
    add_method(ctx, "foo2", [], NoneType(), is_explicit_override=False)


def plugin(version: str) -> type[AddOverrideMethodPlugin]:
    return AddOverrideMethodPlugin
