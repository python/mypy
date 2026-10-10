from __future__ import annotations

from typing import Callable

from mypy.plugin import AttributeContext, Plugin
from mypy.types import AnyType, Type, TypeOfAny


class AttrPlugin(Plugin):
    def get_attribute_hook(self, fullname: str) -> Callable[[AttributeContext], Type] | None:
        if fullname == "m.Magic.magic_field":
            return magic_field_callback
        if fullname == "m.Magic.nonexistent_field":
            return nonexistent_field_callback
        if fullname == "m.Magic.no_assignment_field":
            return no_assignment_field_callback
        return None


def magic_field_callback(ctx: AttributeContext) -> Type:
    return ctx.api.named_generic_type("builtins.str", [])


def nonexistent_field_callback(ctx: AttributeContext) -> Type:
    ctx.api.fail("Field does not exist", ctx.context)
    return AnyType(TypeOfAny.from_error)


def no_assignment_field_callback(ctx: AttributeContext) -> Type:
    if ctx.is_lvalue:
        ctx.api.fail(f"Cannot assign to field", ctx.context)
        return AnyType(TypeOfAny.from_error)
    return ctx.default_attr_type


def plugin(version: str) -> type[AttrPlugin]:
    return AttrPlugin
