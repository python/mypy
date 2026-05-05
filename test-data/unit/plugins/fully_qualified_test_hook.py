from __future__ import annotations

from typing import Callable

from mypy.plugin import MethodSigContext, Plugin
from mypy.types import CallableType


class FullyQualifiedTestPlugin(Plugin):
    def get_method_signature_hook(
        self, fullname: str
    ) -> Callable[[MethodSigContext], CallableType] | None:
        # Ensure that all names are fully qualified
        if "FullyQualifiedTest" in fullname:
            assert fullname.startswith("__main__.") and " of " not in fullname, fullname
            return my_hook

        return None


def my_hook(ctx: MethodSigContext) -> CallableType:
    return ctx.default_signature.copy_modified(
        ret_type=ctx.api.named_generic_type("builtins.int", [])
    )


def plugin(version: str) -> type[FullyQualifiedTestPlugin]:
    return FullyQualifiedTestPlugin
