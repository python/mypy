from functools import partial
from typing import Callable, Optional

from mypy import message_registry
from mypy.nodes import StrExpr, IntExpr, DictExpr, UnaryExpr
from mypy.plugin import (
    Plugin, FunctionContext, MethodContext, MethodSigContext, AttributeContext, ClassDefContext
)
from mypy.plugins.common import try_getting_str_literal
from mypy.types import (
    Type, Instance, AnyType, TypeOfAny, CallableType, NoneTyp, UnionType, TypedDictType,
    TypeVarType
)


class DefaultPlugin(Plugin):
    """Type checker plugin that is enabled by default."""

    def get_function_hook(self, fullname: str
                          ) -> Optional[Callable[[FunctionContext], Type]]:
        from mypy.plugins import ctypes

        if fullname == 'contextlib.contextmanager':
            return contextmanager_callback
        elif fullname == 'builtins.open' and self.python_version[0] == 3:
            return open_callback
        elif fullname == 'ctypes.Array':
            return ctypes.array_constructor_callback
        return None

    def get_method_signature_hook(self, fullname: str
                                  ) -> Optional[Callable[[MethodSigContext], CallableType]]:
        from mypy.plugins import ctypes

        if fullname == 'typing.Mapping.get':
            return typed_dict_get_signature_callback
        elif fullname == 'mypy_extensions._TypedDict.setdefault':
            return typed_dict_setdefault_signature_callback
        elif fullname == 'mypy_extensions._TypedDict.pop':
            return typed_dict_pop_signature_callback
        elif fullname == 'mypy_extensions._TypedDict.update':
            return typed_dict_update_signature_callback
        elif fullname == 'mypy_extensions._TypedDict.__delitem__':
            return typed_dict_delitem_signature_callback
        elif fullname == 'ctypes.Array.__setitem__':
            return ctypes.array_setitem_callback
        return None

    def get_method_hook(self, fullname: str
                        ) -> Optional[Callable[[MethodContext], Type]]:
        from mypy.plugins import ctypes

        if fullname == 'typing.Mapping.get':
            return typed_dict_get_callback
        elif fullname == 'builtins.int.__pow__':
            return int_pow_callback
        elif fullname == 'mypy_extensions._TypedDict.setdefault':
            return typed_dict_setdefault_callback
        elif fullname == 'mypy_extensions._TypedDict.pop':
            return typed_dict_pop_callback
        elif fullname == 'mypy_extensions._TypedDict.__delitem__':
            return typed_dict_delitem_callback
        elif fullname == 'ctypes.Array.__getitem__':
            return ctypes.array_getitem_callback
        elif fullname == 'ctypes.Array.__iter__':
            return ctypes.array_iter_callback
        return None

    def get_attribute_hook(self, fullname: str
                           ) -> Optional[Callable[[AttributeContext], Type]]:
        from mypy.plugins import ctypes

        if fullname == 'ctypes.Array.value':
            return ctypes.array_value_callback
        elif fullname == 'ctypes.Array.raw':
            return ctypes.array_raw_callback
        return None

    def get_class_decorator_hook(self, fullname: str
                                 ) -> Optional[Callable[[ClassDefContext], None]]:
        from mypy.plugins import attrs
        from mypy.plugins import dataclasses

        if fullname in attrs.attr_class_makers:
            return attrs.attr_class_maker_callback
        elif fullname in attrs.attr_dataclass_makers:
            return partial(
                attrs.attr_class_maker_callback,
                auto_attribs_default=True
            )
        elif fullname in dataclasses.dataclass_makers:
            return dataclasses.dataclass_class_maker_callback
        return None


def open_callback(ctx: FunctionContext) -> Type:
    """Infer a better return type for 'open'.

    Infer TextIO or BinaryIO as the return value if the mode argument is not
    given or is a literal.
    """
    mode = None
    if not ctx.arg_types or len(ctx.arg_types[1]) != 1:
        mode = 'r'
    elif isinstance(ctx.args[1][0], StrExpr):
        mode = ctx.args[1][0].value
    if mode is not None:
        assert isinstance(ctx.default_return_type, Instance)
        if 'b' in mode:
            return ctx.api.named_generic_type('typing.BinaryIO', [])
        else:
            return ctx.api.named_generic_type('typing.TextIO', [])
    return ctx.default_return_type


def contextmanager_callback(ctx: FunctionContext) -> Type:
    """Infer a better return type for 'contextlib.contextmanager'."""
    # Be defensive, just in case.
    if ctx.arg_types and len(ctx.arg_types[0]) == 1:
        arg_type = ctx.arg_types[0][0]
        if (isinstance(arg_type, CallableType)
                and isinstance(ctx.default_return_type, CallableType)):
            # The stub signature doesn't preserve information about arguments so
            # add them back here.
            return ctx.default_return_type.copy_modified(
                arg_types=arg_type.arg_types,
                arg_kinds=arg_type.arg_kinds,
                arg_names=arg_type.arg_names,
                variables=arg_type.variables,
                is_ellipsis_args=arg_type.is_ellipsis_args)
    return ctx.default_return_type


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
        value_type = ctx.type.items.get(key)
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
            tv = TypeVarType(signature.variables[0])
            return signature.copy_modified(
                arg_types=[signature.arg_types[0],
                           UnionType.make_simplified_union([value_type, tv])],
                ret_type=ret_type)
    return signature


def typed_dict_get_callback(ctx: MethodContext) -> Type:
    """Infer a precise return type for TypedDict.get with literal first argument."""
    if (isinstance(ctx.type, TypedDictType)
            and len(ctx.arg_types) >= 1
            and len(ctx.arg_types[0]) == 1):
        key = try_getting_str_literal(ctx.args[0][0], ctx.arg_types[0][0])
        if key is None:
            return ctx.default_return_type

        value_type = ctx.type.items.get(key)
        if value_type:
            if len(ctx.arg_types) == 1:
                return UnionType.make_simplified_union([value_type, NoneTyp()])
            elif (len(ctx.arg_types) == 2 and len(ctx.arg_types[1]) == 1
                  and len(ctx.args[1]) == 1):
                default_arg = ctx.args[1][0]
                if (isinstance(default_arg, DictExpr) and len(default_arg.items) == 0
                        and isinstance(value_type, TypedDictType)):
                    # Special case '{}' as the default for a typed dict type.
                    return value_type.copy_modified(required_keys=set())
                else:
                    return UnionType.make_simplified_union([value_type, ctx.arg_types[1][0]])
        else:
            ctx.api.msg.typeddict_key_not_found(ctx.type, key, ctx.context)
            return AnyType(TypeOfAny.from_error)
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
            tv = TypeVarType(signature.variables[0])
            typ = UnionType.make_simplified_union([value_type, tv])
            return signature.copy_modified(
                arg_types=[str_type, typ],
                ret_type=typ)
    return signature.copy_modified(arg_types=[str_type, signature.arg_types[1]])


def typed_dict_pop_callback(ctx: MethodContext) -> Type:
    """Type check and infer a precise return type for TypedDict.pop."""
    if (isinstance(ctx.type, TypedDictType)
            and len(ctx.arg_types) >= 1
            and len(ctx.arg_types[0]) == 1):
        key = try_getting_str_literal(ctx.args[0][0], ctx.arg_types[0][0])
        if key is None:
            ctx.api.fail(message_registry.TYPEDDICT_KEY_MUST_BE_STRING_LITERAL, ctx.context)
            return AnyType(TypeOfAny.from_error)

        if key in ctx.type.required_keys:
            ctx.api.msg.typeddict_key_cannot_be_deleted(ctx.type, key, ctx.context)
        value_type = ctx.type.items.get(key)
        if value_type:
            if len(ctx.args[1]) == 0:
                return value_type
            elif (len(ctx.arg_types) == 2 and len(ctx.arg_types[1]) == 1
                  and len(ctx.args[1]) == 1):
                return UnionType.make_simplified_union([value_type, ctx.arg_types[1][0]])
        else:
            ctx.api.msg.typeddict_key_not_found(ctx.type, key, ctx.context)
            return AnyType(TypeOfAny.from_error)
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
            and len(ctx.arg_types[0]) == 1):
        key = try_getting_str_literal(ctx.args[0][0], ctx.arg_types[0][0])
        if key is None:
            ctx.api.fail(message_registry.TYPEDDICT_KEY_MUST_BE_STRING_LITERAL, ctx.context)
            return AnyType(TypeOfAny.from_error)

        value_type = ctx.type.items.get(key)
        if value_type:
            return value_type
        else:
            ctx.api.msg.typeddict_key_not_found(ctx.type, key, ctx.context)
            return AnyType(TypeOfAny.from_error)
    return ctx.default_return_type


def typed_dict_delitem_signature_callback(ctx: MethodSigContext) -> CallableType:
    # Replace NoReturn as the argument type.
    str_type = ctx.api.named_generic_type('builtins.str', [])
    return ctx.default_signature.copy_modified(arg_types=[str_type])


def typed_dict_delitem_callback(ctx: MethodContext) -> Type:
    """Type check TypedDict.__delitem__."""
    if (isinstance(ctx.type, TypedDictType)
            and len(ctx.arg_types) == 1
            and len(ctx.arg_types[0]) == 1):
        key = try_getting_str_literal(ctx.args[0][0], ctx.arg_types[0][0])
        if key is None:
            ctx.api.fail(message_registry.TYPEDDICT_KEY_MUST_BE_STRING_LITERAL, ctx.context)
            return AnyType(TypeOfAny.from_error)

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
        arg_type = signature.arg_types[0]
        assert isinstance(arg_type, TypedDictType)
        arg_type = arg_type.as_anonymous()
        arg_type = arg_type.copy_modified(required_keys=set())
        return signature.copy_modified(arg_types=[arg_type])
    return signature


def int_pow_callback(ctx: MethodContext) -> Type:
    """Infer a more precise return type for int.__pow__."""
    if (len(ctx.arg_types) == 1
            and len(ctx.arg_types[0]) == 1):
        arg = ctx.args[0][0]
        if isinstance(arg, IntExpr):
            exponent = arg.value
        elif isinstance(arg, UnaryExpr) and arg.op == '-' and isinstance(arg.expr, IntExpr):
            exponent = -arg.expr.value
        else:
            # Right operand not an int literal or a negated literal -- give up.
            return ctx.default_return_type
        if exponent >= 0:
            return ctx.api.named_generic_type('builtins.int', [])
        else:
            return ctx.api.named_generic_type('builtins.float', [])
    return ctx.default_return_type
