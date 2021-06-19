from mypy.types import CallableType, Type
from typing import Callable, Optional
from mypy.plugin import MethodContext, Plugin


class MethodDecoratorPlugin(Plugin):
    def get_method_hook(self, fullname: str) -> Optional[Callable[[MethodContext], Type]]:
        if 'Foo.a' in fullname:
            return method_decorator_callback
        return None

def method_decorator_callback(ctx: MethodContext) -> Type:
    if isinstance(ctx.default_return_type, CallableType):
        str_type = ctx.api.named_generic_type('builtins.str', [])
        return ctx.default_return_type.copy_modified(ret_type=str_type)
    return ctx.default_return_type

def plugin(version):
    return MethodDecoratorPlugin
