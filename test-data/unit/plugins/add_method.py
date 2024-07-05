from __future__ import annotations

from typing import Callable

from mypy.plugin import ClassDefContext, Plugin
from mypy.plugins.common import add_method
from mypy.types import NoneType


class AddOverrideMethodPlugin(Plugin):
    def get_class_decorator_hook_2(self, fullname: str) -> Callable[[ClassDefContext], bool] | None:
        if fullname == "__main__.inject_foo":
            return add_extra_methods_hook
        return None


def add_extra_methods_hook(ctx: ClassDefContext) -> bool:
    add_method(ctx, "foo_implicit", [], NoneType())
    return True


def plugin(version: str) -> type[AddOverrideMethodPlugin]:
    return AddOverrideMethodPlugin
