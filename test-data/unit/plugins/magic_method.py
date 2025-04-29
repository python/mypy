from mypy.types import LiteralType, AnyType, TypeOfAny, Type
from mypy.plugin import Plugin, MethodContext
from typing import Callable

# If radd exists, there shouldn't be an error. If it doesn't exist, then there will be an error
def type_add(ctx: MethodContext, *args) -> Type:
    ctx.api.fail("test", ctx.context)
    return AnyType(TypeOfAny.from_error)

def type_radd(ctx: MethodContext, *args) -> Type:
    lhs = ctx.type
    rhs = ctx.arg_types[-1][0]
    if not (isinstance(lhs, LiteralType) and isinstance(rhs, LiteralType)):
        ctx.api.fail("operands not literals", ctx.context)
        return AnyType(TypeOfAny.from_error)
    if not (isinstance(lhs.value, int) and isinstance(rhs.value, int)):
        ctx.api.fail("operands not literal ints", ctx.context)
        return AnyType(TypeOfAny.from_error)
    ret = lhs.value + rhs.value
    return LiteralType(ret, fallback=ctx.api.named_generic_type('builtins.int', []))


class TestPlugin(Plugin):
    def get_method_hook(self, fullname: str) -> Callable[[MethodContext], Type] | None:

        if fullname == 'builtins.int.__add__':
            return type_add
        if fullname == 'builtins.int.__radd__':
            return type_radd
        return None

def plugin(version: str) -> type[TestPlugin]:
    return TestPlugin
