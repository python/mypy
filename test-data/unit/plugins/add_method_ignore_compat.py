from __future__ import annotations

from typing import Callable

from mypy.nodes import PluginFlags
from mypy.plugin import ClassDefContext, Plugin
from mypy.plugins.common import add_attribute_to_class, add_method_to_class
from mypy.types import NoneType


class AddOverrideMethodPlugin(Plugin):
    def get_class_decorator_hook_2(self, fullname: str) -> Callable[[ClassDefContext], bool] | None:
        if fullname == "__main__.inject_foo":
            return add_extra_methods_hook
        return None


def add_extra_methods_hook(ctx: ClassDefContext) -> bool:
    add_method_to_class(
        ctx.api,
        ctx.cls,
        "meth_ok",
        [],
        NoneType(),
        flags=PluginFlags(skip_override_checks=True)
    )
    add_method_to_class(
        ctx.api,
        ctx.cls,
        "meth_bad",
        [],
        NoneType(),
        flags=PluginFlags(skip_override_checks=False)
    )
    add_attribute_to_class(
        ctx.api,
        ctx.cls,
        "attr",
        NoneType(),
        flags=PluginFlags(skip_override_checks=True)
    )
    return True


def plugin(version: str) -> type[AddOverrideMethodPlugin]:
    return AddOverrideMethodPlugin
