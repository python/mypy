from typing import Optional, Callable

from mypy.plugin import Plugin, AttributeContext
from mypy.types import Type, AnyType, TypeOfAny


class AttrPlugin(Plugin):
    def get_attribute_hook(self, fullname: str) -> Optional[Callable[[AttributeContext], Type]]:
        if fullname == 'm.Magic.magic_field':
            return magic_field_callback
        if fullname == 'm.Magic.nonexistent_field':
            return nonexistent_field_callback
        return None


def magic_field_callback(ctx: AttributeContext) -> Type:
    return ctx.api.named_generic_type("builtins.str", [])


def nonexistent_field_callback(ctx: AttributeContext) -> Type:
    ctx.api.fail("Field does not exist", ctx.context)
    return AnyType(TypeOfAny.from_error)


def plugin(version):
    return AttrPlugin
