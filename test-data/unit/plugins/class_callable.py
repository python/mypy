from __future__ import annotations

from typing import Callable

from mypy.nodes import NameExpr
from mypy.plugin import FunctionContext, Plugin
from mypy.types import Instance, NoneType, Type, UnionType, get_proper_type


class AttrPlugin(Plugin):
    def get_function_hook(self, fullname: str) -> Callable[[FunctionContext], Type] | None:
        if fullname.startswith("mod.Attr"):
            return attr_hook
        return None


def attr_hook(ctx: FunctionContext) -> Type:
    default = get_proper_type(ctx.default_return_type)
    assert isinstance(default, Instance)
    if default.type.fullname == "mod.Attr":
        attr_base = default
    else:
        attr_base = None
    for base in default.type.bases:
        if base.type.fullname == "mod.Attr":
            attr_base = base
            break
    assert attr_base is not None
    last_arg_exprs = ctx.args[-1]
    if any(isinstance(expr, NameExpr) and expr.name == "True" for expr in last_arg_exprs):
        return attr_base
    assert len(attr_base.args) == 1
    arg_type = attr_base.args[0]
    return Instance(
        attr_base.type,
        [UnionType([arg_type, NoneType()])],
        line=default.line,
        column=default.column,
    )


def plugin(version: str) -> type[AttrPlugin]:
    return AttrPlugin
