from __future__ import annotations

from typing import Callable

from mypy.plugin import MethodSigContext, Plugin
from mypy.types import CallableType


class DefiningClassPlugin(Plugin):
    def get_method_signature_hook(
        self, fullname: str
    ) -> Callable[[MethodSigContext], CallableType] | None:
        if fullname == "__main__.Base.method":
            return defining_class_hook
        return None


def defining_class_hook(ctx: MethodSigContext) -> CallableType:
    return ctx.default_signature.copy_modified(
        ret_type=ctx.api.named_generic_type("builtins.int", [])
    )


def plugin(version: str) -> type[DefiningClassPlugin]:
    return DefiningClassPlugin
