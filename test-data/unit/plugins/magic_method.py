from mypy.types import LiteralType, AnyType, TypeOfAny
from mypy.plugin import Plugin

def type_add(ctx, *args):
    lhs = ctx.type
    rhs = ctx.arg_types[0][0]
    ret = lhs.value + rhs.value
    ctx.api.fail("test", ctx.context)
    return AnyType(TypeOfAny.from_error)

def type_radd(ctx, *args):
    lhs = ctx.type
    rhs = ctx.arg_types[0][0]
    ret = lhs.value + rhs.value
    return LiteralType(ret, fallback=ctx.api.named_generic_type('builtins.int', []))


class TestPlugin(Plugin):

    def get_method_hook(self, fullname):
        if fullname == 'builtins.int.__add__':
            return type_add
        if fullname == 'builtins.int.__radd__':
            return type_radd
        return None

def plugin(version: str):
    return TestPlugin
