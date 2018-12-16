import sys
from typing import Optional, Callable

from mypy.nodes import Context
from mypy.plugin import Plugin, MethodContext, FunctionContext
from mypy.types import Type


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
    ctx.api.fail(str(ctx.arg_kinds), ctx.context)
    return ctx.default_return_type


def extract_arg_kinds_from_method(ctx: MethodContext) -> Type:
    ctx.api.fail(str(ctx.arg_kinds), ctx.context)
    return ctx.default_return_type


def plugin(version):
    return ArgKindsPlugin
