from typing import Optional

from mypy.plugin import Plugin, AttributeHook
from mypy.types import Type, Instance


class AttrPlugin(Plugin):
    def get_attribute_hook(self, fullname: str) -> Optional[AttributeHook]:
        if fullname == 'm.Signal.__call__':
            return signal_call_callback
        return None


def signal_call_callback(object_type: Type, inferred_attribute: Type) -> Type:
    if isinstance(object_type, Instance) and object_type.type.fullname() == 'm.Signal':
        return object_type.args[0]
    return inferred_attribute


def plugin(version):
    return AttrPlugin
