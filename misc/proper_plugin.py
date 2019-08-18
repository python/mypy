from mypy.plugin import Plugin, FunctionContext
from mypy.types import (
    Type, Instance, CallableType, UnionType, get_proper_type, ProperType,
    get_proper_types, TupleType
)
from mypy.subtypes import is_proper_subtype

import os.path
from typing_extensions import Type as typing_Type
from typing import Optional, Callable

FILE_WHITELIST = []


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
            if is_special_target(right):
                return ctx.default_return_type
            ctx.api.fail('Never apply isinstance() to unexpanded types;'
                         ' use mypy.types.get_proper_type() first', ctx.context)
    return ctx.default_return_type


def is_special_target(right: ProperType) -> bool:
    if isinstance(right, CallableType) and right.is_type_obj():
        if right.type_object().fullname() == 'builtins.tuple':
            # Used with Union[Type, Tuple[Type, ...]].
            return True
        if right.type_object().fullname() in ('mypy.types.Type',
                                              'mypy.types.ProperType',
                                              'mypy.types.TypeAliasType'):
            # Special case: things like assert isinstance(typ, ProperType) are always OK.
            return True
        if right.type_object().fullname() in ('mypy.types.UnboundType',
                                              'mypy.types.TypeVarType',
                                              'mypy.types.EllipsisType',
                                              'mypy.types.StarType',
                                              'mypy.types.TypeList',
                                              'mypy.types.CallableArgument',
                                              'mypy.types.PartialType',
                                              'mypy.types.ErasedType'):
            # Special case: these are not valid targets for a type alias and thus safe.
            # TODO: introduce a SyntheticType base to simplify this?
            return True
    elif isinstance(right, TupleType):
        return all(is_special_target(t) for t in get_proper_types(right.items))
    return False


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
