from __future__ import annotations

from typing import Callable

from mypy.nodes import StrExpr
from mypy.plugin import FunctionContext, MethodContext, Plugin
from mypy.types import Type


class ArgNamesPlugin(Plugin):
    def get_function_hook(self, fullname: str) -> Callable[[FunctionContext], Type] | None:
        if fullname in {
            "mod.func",
            "mod.func_unfilled",
            "mod.func_star_expr",
            "mod.ClassInit",
            "mod.Outer.NestedClassInit",
        }:
            return extract_classname_and_set_as_return_type_function
        return None

    def get_method_hook(self, fullname: str) -> Callable[[MethodContext], Type] | None:
        if fullname in {
            "mod.Class.method",
            "mod.Class.myclassmethod",
            "mod.Class.mystaticmethod",
            "mod.ClassUnfilled.method",
            "mod.ClassStarExpr.method",
            "mod.ClassChild.method",
            "mod.ClassChild.myclassmethod",
        }:
            return extract_classname_and_set_as_return_type_method
        return None


def extract_classname_and_set_as_return_type_function(ctx: FunctionContext) -> Type:
    arg = ctx.args[ctx.callee_arg_names.index("classname")][0]
    if not isinstance(arg, StrExpr):
        return ctx.default_return_type
    return ctx.api.named_generic_type(arg.value, [])


def extract_classname_and_set_as_return_type_method(ctx: MethodContext) -> Type:
    arg = ctx.args[ctx.callee_arg_names.index("classname")][0]
    if not isinstance(arg, StrExpr):
        return ctx.default_return_type
    return ctx.api.named_generic_type(arg.value, [])


def plugin(version: str) -> type[ArgNamesPlugin]:
    return ArgNamesPlugin
