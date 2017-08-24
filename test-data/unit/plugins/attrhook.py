from typing import Optional, Callable

from mypy.plugin import Plugin, AttributeContext
from mypy.types import Type, Instance


class AttrPlugin(Plugin):
    def get_attribute_hook(self, fullname: str) -> Optional[Callable[[AttributeContext], Type]]:
        if fullname == 'm.Signal.__call__':
            return signal_call_callback
        return None


def signal_call_callback(ctx: AttributeContext) -> Type:
    if isinstance(ctx.type, Instance) and ctx.type.type.fullname() == 'm.Signal':
        return ctx.type.args[0]
    return ctx.inferred_attr_type


def plugin(version):
    return AttrPlugin
