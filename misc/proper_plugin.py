from mypy.plugin import Plugin, FunctionContext
from mypy.types import Type, Instance, CallableType, UnionType, get_proper_type

import os.path
from typing_extensions import Type as typing_Type
from typing import Optional, Callable

FILE_WHITELIST = [
    'checker.py',
    'checkexpr.py',
    'checkmember.py',
    'messages.py',
    'semanal.py',
    'typeanal.py'
]


class ProperTypePlugin(Plugin):
    """
    A plugin to ensure that every type is expanded before doing any special-casing.

    This solves the problem that we have hundreds of call sites like:

        if isinstance(typ, UnionType):
            ...  # special-case union

    But after introducing a new type TypeAliasType (and removing immediate expansion)
    all these became dangerous because typ may be e.g. an alias to union.
    """
    def get_function_hook(self, fullname: str
                          ) -> Optional[Callable[[FunctionContext], Type]]:
        if fullname == 'builtins.isinstance':
            return isinstance_proper_hook
        return None


def isinstance_proper_hook(ctx: FunctionContext) -> Type:
    if os.path.split(ctx.api.path)[-1] in FILE_WHITELIST:
        return ctx.default_return_type
    for arg in ctx.arg_types[0]:
        if is_improper_type(arg):
            right = get_proper_type(ctx.arg_types[1][0])
            if isinstance(right, CallableType) and right.is_type_obj():
                if right.type_object().fullname() in ('mypy.types.Type',
                                                      'mypy.types.ProperType',
                                                      'mypy.types.TypeAliasType'):
                    # Special case: things like assert isinstance(typ, ProperType) are always OK.
                    return ctx.default_return_type
                if right.type_object().fullname() in ('mypy.types.UnboundType',
                                                      'mypy.types.TypeVarType'):
                    # Special case: these are not valid targets for a type alias and thus safe.
                    return ctx.default_return_type
            ctx.api.fail('Never apply isinstance() to unexpanded types;'
                         ' use mypy.types.get_proper_type() first', ctx.context)
    return ctx.default_return_type


def is_improper_type(typ: Type) -> bool:
    """Is this a type that is not a subtype of ProperType?"""
    typ = get_proper_type(typ)
    if isinstance(typ, Instance):
        info = typ.type
        return info.has_base('mypy.types.Type') and not info.has_base('mypy.types.ProperType')
    if isinstance(typ, UnionType):
        return any(is_improper_type(t) for t in typ.items)
    return False


def plugin(version: str) -> typing_Type[ProperTypePlugin]:
    return ProperTypePlugin
