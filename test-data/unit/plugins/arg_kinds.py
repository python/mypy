from typing import Optional, Callable
from mypy.plugin import Plugin, MethodContext, FunctionContext
from mypy.types import Type
from mypy.message_registry import ErrorMessage

class ArgKindsPlugin(Plugin):
    def get_function_hook(self, fullname: str
                          ) -> Optional[Callable[[FunctionContext], Type]]:
        if 'func' in fullname:
            return extract_arg_kinds_from_function
        return None

    def get_method_hook(self, fullname: str
                        ) -> Optional[Callable[[MethodContext], Type]]:
        if 'Class.method' in fullname:
            return extract_arg_kinds_from_method
        return None


def extract_arg_kinds_from_function(ctx: FunctionContext) -> Type:
    error_message = ErrorMessage(str([[x.value for x in y] for y in ctx.arg_kinds]))
    ctx.api.fail(error_message, ctx.context)
    return ctx.default_return_type


def extract_arg_kinds_from_method(ctx: MethodContext) -> Type:
    error_message = ErrorMessage(str([[x.value for x in y] for y in ctx.arg_kinds]))
    ctx.api.fail(error_message, ctx.context)
    return ctx.default_return_type


def plugin(version):
    return ArgKindsPlugin
