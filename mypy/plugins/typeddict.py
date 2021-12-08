from typing import List

from mypy import message_registry
from mypy.checkexpr import MethodSigContext, MethodContext
from mypy.nodes import StrExpr, DictExpr, UnicodeExpr
from mypy.plugins.common import try_getting_str_literals
from mypy.subtypes import is_subtype
from mypy.typeops import make_simplified_union
from mypy.types import (
    CallableType, TypedDictType, get_proper_type, TypeVarType, Type, NoneType,
    TypeOfAny, AnyType, UnionType, get_proper_types, Instance, LiteralType
)


def typed_dict_get_signature_callback(ctx: MethodSigContext) -> CallableType:
    """Try to infer a better signature type for TypedDict.get.

    This is used to get better type context for the second argument that
    depends on a TypedDict value type.
    """
    signature = ctx.default_signature
    if (isinstance(ctx.type, TypedDictType)
            and len(ctx.args) == 2
            and len(ctx.args[0]) == 1
            and isinstance(ctx.args[0][0], StrExpr)
            and len(signature.arg_types) == 2
            and len(signature.variables) == 1
            and len(ctx.args[1]) == 1):
        key = ctx.args[0][0].value
        value_type = get_proper_type(ctx.type.items.get(key))
        ret_type = signature.ret_type
        if value_type:
            default_arg = ctx.args[1][0]
            if (isinstance(value_type, TypedDictType)
                    and isinstance(default_arg, DictExpr)
                    and len(default_arg.items) == 0):
                # Caller has empty dict {} as default for typed dict.
                value_type = value_type.copy_modified(required_keys=set())
            # Tweak the signature to include the value type as context. It's
            # only needed for type inference since there's a union with a type
            # variable that accepts everything.
            tv = signature.variables[0]
            assert isinstance(tv, TypeVarType)
            return signature.copy_modified(
                arg_types=[signature.arg_types[0],
                           make_simplified_union([value_type, tv])],
                ret_type=ret_type)
    return signature


def typed_dict_get_callback(ctx: MethodContext) -> Type:
    """Infer a precise return type for TypedDict.get with literal first argument."""
    if (isinstance(ctx.type, TypedDictType)
            and len(ctx.arg_types) >= 1
            and len(ctx.arg_types[0]) == 1):
        keys = try_getting_str_literals(ctx.args[0][0], ctx.arg_types[0][0])
        if keys is None:
            return ctx.default_return_type

        output_types: List[Type] = []
        for key in keys:
            value_type = get_proper_type(ctx.type.items.get(key))
            if value_type is None:
                return ctx.default_return_type

            if len(ctx.arg_types) == 1:
                output_types.append(value_type)
            elif (len(ctx.arg_types) == 2 and len(ctx.arg_types[1]) == 1
                  and len(ctx.args[1]) == 1):
                default_arg = ctx.args[1][0]
                if (isinstance(default_arg, DictExpr) and len(default_arg.items) == 0
                        and isinstance(value_type, TypedDictType)):
                    # Special case '{}' as the default for a typed dict type.
                    output_types.append(value_type.copy_modified(required_keys=set()))
                else:
                    output_types.append(value_type)
                    output_types.append(ctx.arg_types[1][0])

        if len(ctx.arg_types) == 1:
            output_types.append(NoneType())

        return make_simplified_union(output_types)
    return ctx.default_return_type


def typed_dict_getitem_callback(ctx: MethodContext) -> Type:
    if (isinstance(ctx.type, TypedDictType)
            and len(ctx.arg_types) == 1
            and len(ctx.arg_types[0]) == 1):
        td_type = ctx.type
        index = get_proper_type(ctx.arg_types[0][0])
        if isinstance(index, (StrExpr, UnicodeExpr)):
            key_names = [index.value]
        else:
            # typ = get_proper_type(self.accept(index))
            typ = index
            if isinstance(typ, UnionType):
                key_types: List[Type] = list(typ.items)
            else:
                key_types = [typ]

            key_names = []
            for key_type in get_proper_types(key_types):
                if key_type is None:
                    return ctx.default_return_type
                if isinstance(key_type, Instance) and key_type.last_known_value is not None:
                    key_type = key_type.last_known_value

                if (isinstance(key_type, LiteralType)
                        and isinstance(key_type.value, str)
                        and key_type.fallback.type.fullname != 'builtins.bytes'):
                    key_names.append(key_type.value)
                else:
                    ctx.api.msg.typeddict_key_must_be_string_literal(td_type, ctx.context)
                    return AnyType(TypeOfAny.from_error)

        value_types = []
        for key_name in key_names:
            value_type = td_type.items.get(key_name)
            if value_type is None:
                ctx.api.msg.typeddict_key_not_found(td_type, key_name, ctx.context)
                return AnyType(TypeOfAny.from_error)
            else:
                value_types.append(value_type)
        return make_simplified_union(value_types)
    return ctx.default_return_type


def typed_dict_pop_signature_callback(ctx: MethodSigContext) -> CallableType:
    """Try to infer a better signature type for TypedDict.pop.

    This is used to get better type context for the second argument that
    depends on a TypedDict value type.
    """
    signature = ctx.default_signature
    str_type = ctx.api.named_generic_type('builtins.str', [])
    if (isinstance(ctx.type, TypedDictType)
            and len(ctx.args) == 2
            and len(ctx.args[0]) == 1
            and isinstance(ctx.args[0][0], StrExpr)
            and len(signature.arg_types) == 2
            and len(signature.variables) == 1
            and len(ctx.args[1]) == 1):
        key = ctx.args[0][0].value
        value_type = ctx.type.items.get(key)
        if value_type:
            # Tweak the signature to include the value type as context. It's
            # only needed for type inference since there's a union with a type
            # variable that accepts everything.
            tv = signature.variables[0]
            assert isinstance(tv, TypeVarType)
            typ = make_simplified_union([value_type, tv])
            return signature.copy_modified(
                arg_types=[str_type, typ],
                ret_type=typ)
    return signature.copy_modified(arg_types=[str_type, signature.arg_types[1]])


def typed_dict_pop_callback(ctx: MethodContext) -> Type:
    """Type check and infer a precise return type for TypedDict.pop."""
    if (isinstance(ctx.type, TypedDictType)
            and len(ctx.arg_types) >= 1
            and len(ctx.arg_types[0]) == 1):
        keys = try_getting_str_literals(ctx.args[0][0], ctx.arg_types[0][0])
        if keys is None:
            ctx.api.fail(message_registry.TYPEDDICT_KEY_MUST_BE_STRING_LITERAL, ctx.context)
            return AnyType(TypeOfAny.from_error)

        value_types = []
        for key in keys:
            if key in ctx.type.required_keys:
                ctx.api.msg.typeddict_key_cannot_be_deleted(ctx.type, key, ctx.context)

            value_type = ctx.type.items.get(key)
            if value_type:
                value_types.append(value_type)
            else:
                ctx.api.msg.typeddict_key_not_found(ctx.type, key, ctx.context)
                return AnyType(TypeOfAny.from_error)

        if len(ctx.args[1]) == 0:
            return make_simplified_union(value_types)
        elif (len(ctx.arg_types) == 2 and len(ctx.arg_types[1]) == 1
              and len(ctx.args[1]) == 1):
            return make_simplified_union([*value_types, ctx.arg_types[1][0]])
    return ctx.default_return_type


def typed_dict_setdefault_signature_callback(ctx: MethodSigContext) -> CallableType:
    """Try to infer a better signature type for TypedDict.setdefault.

    This is used to get better type context for the second argument that
    depends on a TypedDict value type.
    """
    signature = ctx.default_signature
    str_type = ctx.api.named_generic_type('builtins.str', [])
    if (isinstance(ctx.type, TypedDictType)
            and len(ctx.args) == 2
            and len(ctx.args[0]) == 1
            and isinstance(ctx.args[0][0], StrExpr)
            and len(signature.arg_types) == 2
            and len(ctx.args[1]) == 1):
        key = ctx.args[0][0].value
        value_type = ctx.type.items.get(key)
        if value_type:
            return signature.copy_modified(arg_types=[str_type, value_type])
    return signature.copy_modified(arg_types=[str_type, signature.arg_types[1]])


def typed_dict_setdefault_callback(ctx: MethodContext) -> Type:
    """Type check TypedDict.setdefault and infer a precise return type."""
    if (isinstance(ctx.type, TypedDictType)
            and len(ctx.arg_types) == 2
            and len(ctx.arg_types[0]) == 1
            and len(ctx.arg_types[1]) == 1):
        keys = try_getting_str_literals(ctx.args[0][0], ctx.arg_types[0][0])
        if keys is None:
            ctx.api.fail(message_registry.TYPEDDICT_KEY_MUST_BE_STRING_LITERAL, ctx.context)
            return AnyType(TypeOfAny.from_error)

        default_type = ctx.arg_types[1][0]

        value_types = []
        for key in keys:
            value_type = ctx.type.items.get(key)

            if value_type is None:
                ctx.api.msg.typeddict_key_not_found(ctx.type, key, ctx.context)
                return AnyType(TypeOfAny.from_error)

            # The signature_callback above can't always infer the right signature
            # (e.g. when the expression is a variable that happens to be a Literal str)
            # so we need to handle the check ourselves here and make sure the provided
            # default can be assigned to all key-value pairs we're updating.
            if not is_subtype(default_type, value_type):
                ctx.api.msg.typeddict_setdefault_arguments_inconsistent(
                    default_type, value_type, ctx.context)
                return AnyType(TypeOfAny.from_error)

            value_types.append(value_type)

        return make_simplified_union(value_types)
    return ctx.default_return_type


def typed_dict_delitem_callback(ctx: MethodContext) -> Type:
    """Type check TypedDict.__delitem__."""
    if (isinstance(ctx.type, TypedDictType)
            and len(ctx.arg_types) == 1
            and len(ctx.arg_types[0]) == 1):
        keys = try_getting_str_literals(ctx.args[0][0], ctx.arg_types[0][0])
        if keys is None:
            ctx.api.fail(message_registry.TYPEDDICT_KEY_MUST_BE_STRING_LITERAL, ctx.context)
            return AnyType(TypeOfAny.from_error)

        for key in keys:
            if key in ctx.type.required_keys:
                ctx.api.msg.typeddict_key_cannot_be_deleted(ctx.type, key, ctx.context)
            elif key not in ctx.type.items:
                ctx.api.msg.typeddict_key_not_found(ctx.type, key, ctx.context)
    return ctx.default_return_type


def typed_dict_update_signature_callback(ctx: MethodSigContext) -> CallableType:
    """Try to infer a better signature type for TypedDict.update."""
    signature = ctx.default_signature
    if (isinstance(ctx.type, TypedDictType)
            and len(signature.arg_types) == 1):
        arg_type = get_proper_type(signature.arg_types[0])
        assert isinstance(arg_type, TypedDictType)
        arg_type = arg_type.as_anonymous()
        arg_type = arg_type.copy_modified(required_keys=set())
        return signature.copy_modified(arg_types=[arg_type])
    return signature