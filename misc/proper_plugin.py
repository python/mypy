from mypy.plugin import Plugin, FunctionContext
from mypy.types import Type, Instance

import os.path
from typing_extensions import Type as typing_Type
from typing import Optional, Callable

FILE_WHITELIST = []


class ProperTypePlugin(Plugin):
    def get_function_hook(self, fullname: str
                          ) -> Optional[Callable[[FunctionContext], Type]]:
        if fullname == 'builtins.isinstance':
            return isinstance_proper_hook
        return None


def isinstance_proper_hook(ctx: FunctionContext) -> Type:
    if os.path.split(ctx.api.path)[-1] in FILE_WHITELIST:
        return ctx.default_return_type
    for arg in ctx.arg_types[0]:
        if isinstance(arg, Instance) and arg.type.has_base('mypy.types.Type'):
            if not any(base.fullname() == 'mypy.types.ProperType' for base in arg.type.mro):
                ctx.api.fail('Never apply isinstance() to unexpanded types;'
                             ' use mypy.types.get_proper_type() first', ctx.context)
    return ctx.default_return_type


def plugin(version: str) -> typing_Type[ProperTypePlugin]:
    return ProperTypePlugin
