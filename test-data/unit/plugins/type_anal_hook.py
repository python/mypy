from __future__ import annotations

from typing import Callable

from mypy.plugin import AnalyzeTypeContext, Plugin

# The official name changed to NoneType but we have an alias for plugin compat reasons
# so we'll keep testing that here.
from mypy.types import AnyType, CallableType, NoneTyp, Type, TypeList, TypeOfAny


class TypeAnalyzePlugin(Plugin):
    def get_type_analyze_hook(self, fullname: str) -> Callable[[AnalyzeTypeContext], Type] | None:
        if fullname == "m.Signal":
            return signal_type_analyze_callback
        return None


def signal_type_analyze_callback(ctx: AnalyzeTypeContext) -> Type:
    if len(ctx.type.args) != 1 or not isinstance(ctx.type.args[0], TypeList):
        ctx.api.fail('Invalid "Signal" type (expected "Signal[[t, ...]]")', ctx.context)
        return AnyType(TypeOfAny.from_error)

    args = ctx.type.args[0]
    assert isinstance(args, TypeList)
    analyzed = ctx.api.analyze_callable_args(args)
    if analyzed is None:
        return AnyType(TypeOfAny.from_error)  # Error generated elsewhere
    arg_types, arg_kinds, arg_names = analyzed
    arg_types = [ctx.api.analyze_type(arg) for arg in arg_types]
    type_arg = CallableType(
        arg_types, arg_kinds, arg_names, NoneTyp(), ctx.api.named_type("builtins.function", [])
    )
    return ctx.api.named_type("m.Signal", [type_arg])


def plugin(version: str) -> type[TypeAnalyzePlugin]:
    return TypeAnalyzePlugin
