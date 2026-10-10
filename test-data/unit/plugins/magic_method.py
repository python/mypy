from mypy.types import LiteralType, AnyType, TypeOfAny, Type
from mypy.plugin import Plugin, MethodContext
from typing import Callable, Optional

# If radd exists, there shouldn't be an error. If it doesn't exist, then there will be an error
def type_add(ctx: MethodContext) -> Type:
    ctx.api.fail("fail", ctx.context)
    return AnyType(TypeOfAny.from_error)

def type_radd(ctx: MethodContext) -> Type:
    return LiteralType(7, fallback=ctx.api.named_generic_type('builtins.int', []))


class TestPlugin(Plugin):

    def get_method_hook(self, fullname: str) -> Optional[Callable[[MethodContext], Type]]:
        if fullname == 'builtins.int.__add__':
            return type_add
        if fullname == 'builtins.int.__radd__':
            return type_radd
        return None

def plugin(version: str) -> type[TestPlugin]:
    return TestPlugin
