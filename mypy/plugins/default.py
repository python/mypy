from functools import partial
from typing import Callable, Optional, List

from mypy.nodes import Expression, StrExpr, IntExpr, UnaryExpr
from mypy.plugin import (
    Plugin, FunctionContext, MethodContext, MethodSigContext, AttributeContext, ClassDefContext,
    CheckerPluginInterface,
)
from mypy.types import (
    FunctionLike, Type, Instance, CallableType, TPDICT_FB_NAMES, get_proper_type,
    LiteralType, TupleType
)
from mypy.checkexpr import is_literal_type_like
from mypy.checker import detach_callable


class DefaultPlugin(Plugin):
    """Type checker plugin that is enabled by default."""

    def get_function_hook(self, fullname: str
                          ) -> Optional[Callable[[FunctionContext], Type]]:
        from mypy.plugins import ctypes, singledispatch

        if fullname in ('contextlib.contextmanager', 'contextlib.asynccontextmanager'):
            return contextmanager_callback
        elif fullname == 'builtins.open' and self.python_version[0] == 3:
            return open_callback
        elif fullname == 'ctypes.Array':
            return ctypes.array_constructor_callback
        elif fullname == 'functools.singledispatch':
            return singledispatch.create_singledispatch_function_callback
        return None

    def get_method_signature_hook(self, fullname: str
                                  ) -> Optional[Callable[[MethodSigContext], FunctionLike]]:
        from mypy.plugins import typeddict, ctypes, singledispatch

        if fullname == 'typing.Mapping.get':
            return typeddict.typed_dict_get_signature_callback
        elif fullname == 'typing.Mapping.__getitem__':
            return typeddict.typed_dict_get_signature_callback
        elif fullname in set(n + '.setdefault' for n in TPDICT_FB_NAMES):
            return typeddict.typed_dict_setdefault_signature_callback
        elif fullname in set(n + '.pop' for n in TPDICT_FB_NAMES):
            return typeddict.typed_dict_pop_signature_callback
        elif fullname in set(n + '.update' for n in TPDICT_FB_NAMES):
            return typeddict.typed_dict_update_signature_callback
        elif fullname == 'ctypes.Array.__setitem__':
            return ctypes.array_setitem_callback
        elif fullname == singledispatch.SINGLEDISPATCH_CALLABLE_CALL_METHOD:
            return singledispatch.call_singledispatch_function_callback
        return None

    def get_method_hook(self, fullname: str
                        ) -> Optional[Callable[[MethodContext], Type]]:
        from mypy.plugins import typeddict, ctypes, singledispatch

        if fullname == 'typing.Mapping.get':
            return typeddict.typed_dict_get_callback
        elif fullname == 'typing.Mapping.__getitem__':
            return typeddict.typed_dict_getitem_callback
        elif fullname == 'builtins.int.__pow__':
            return int_pow_callback
        elif fullname == 'builtins.int.__neg__':
            return int_neg_callback
        elif fullname in ('builtins.tuple.__mul__', 'builtins.tuple.__rmul__'):
            return tuple_mul_callback
        elif fullname in set(n + '.setdefault' for n in TPDICT_FB_NAMES):
            return typeddict.typed_dict_setdefault_callback
        elif fullname in set(n + '.pop' for n in TPDICT_FB_NAMES):
            return typeddict.typed_dict_pop_callback
        elif fullname in set(n + '.__delitem__' for n in TPDICT_FB_NAMES):
            return typeddict.typed_dict_delitem_callback
        elif fullname == 'ctypes.Array.__getitem__':
            return ctypes.array_getitem_callback
        elif fullname == 'ctypes.Array.__iter__':
            return ctypes.array_iter_callback
        elif fullname == 'pathlib.Path.open':
            return path_open_callback
        elif fullname == singledispatch.SINGLEDISPATCH_REGISTER_METHOD:
            return singledispatch.singledispatch_register_callback
        elif fullname == singledispatch.REGISTER_CALLABLE_CALL_METHOD:
            return singledispatch.call_singledispatch_function_after_register_argument
        return None

    def get_attribute_hook(self, fullname: str
                           ) -> Optional[Callable[[AttributeContext], Type]]:
        from mypy.plugins import ctypes
        from mypy.plugins import enums

        if fullname == 'ctypes.Array.value':
            return ctypes.array_value_callback
        elif fullname == 'ctypes.Array.raw':
            return ctypes.array_raw_callback
        elif fullname in enums.ENUM_NAME_ACCESS:
            return enums.enum_name_callback
        elif fullname in enums.ENUM_VALUE_ACCESS:
            return enums.enum_value_callback
        return None

    def get_class_decorator_hook(self, fullname: str
                                 ) -> Optional[Callable[[ClassDefContext], None]]:
        from mypy.plugins import attrs
        from mypy.plugins import dataclasses
        from mypy.plugins import functools

        if fullname in attrs.attr_class_makers:
            return attrs.attr_class_maker_callback
        elif fullname in attrs.attr_dataclass_makers:
            return partial(
                attrs.attr_class_maker_callback,
                auto_attribs_default=True,
            )
        elif fullname in attrs.attr_frozen_makers:
            return partial(
                attrs.attr_class_maker_callback,
                auto_attribs_default=None,
                frozen_default=True,
            )
        elif fullname in attrs.attr_define_makers:
            return partial(
                attrs.attr_class_maker_callback,
                auto_attribs_default=None,
            )
        elif fullname in dataclasses.dataclass_makers:
            return dataclasses.dataclass_class_maker_callback
        elif fullname in functools.functools_total_ordering_makers:
            return functools.functools_total_ordering_maker_callback

        return None


def open_callback(ctx: FunctionContext) -> Type:
    """Infer a better return type for 'open'."""
    return _analyze_open_signature(
        arg_types=ctx.arg_types,
        args=ctx.args,
        mode_arg_index=1,
        default_return_type=ctx.default_return_type,
        api=ctx.api,
    )


def path_open_callback(ctx: MethodContext) -> Type:
    """Infer a better return type for 'pathlib.Path.open'."""
    return _analyze_open_signature(
        arg_types=ctx.arg_types,
        args=ctx.args,
        mode_arg_index=0,
        default_return_type=ctx.default_return_type,
        api=ctx.api,
    )


def _analyze_open_signature(arg_types: List[List[Type]],
                            args: List[List[Expression]],
                            mode_arg_index: int,
                            default_return_type: Type,
                            api: CheckerPluginInterface,
                            ) -> Type:
    """A helper for analyzing any function that has approximately
    the same signature as the builtin 'open(...)' function.

    Currently, the only thing the caller can customize is the index
    of the 'mode' argument. If the mode argument is omitted or is a
    string literal, we refine the return type to either 'TextIO' or
    'BinaryIO' as appropriate.
    """
    mode = None
    if not arg_types or len(arg_types[mode_arg_index]) != 1:
        mode = 'r'
    else:
        mode_expr = args[mode_arg_index][0]
        if isinstance(mode_expr, StrExpr):
            mode = mode_expr.value
    if mode is not None:
        assert isinstance(default_return_type, Instance)  # type: ignore
        if 'b' in mode:
            return api.named_generic_type('typing.BinaryIO', [])
        else:
            return api.named_generic_type('typing.TextIO', [])
    return default_return_type


def contextmanager_callback(ctx: FunctionContext) -> Type:
    """Infer a better return type for 'contextlib.contextmanager'."""
    # Be defensive, just in case.
    if ctx.arg_types and len(ctx.arg_types[0]) == 1:
        arg_type = get_proper_type(ctx.arg_types[0][0])
        default_return = get_proper_type(ctx.default_return_type)
        if (isinstance(arg_type, CallableType)
                and isinstance(default_return, CallableType)):
            # The stub signature doesn't preserve information about arguments so
            # add them back here.
            return detach_callable(default_return.copy_modified(
                arg_types=arg_type.arg_types,
                arg_kinds=arg_type.arg_kinds,
                arg_names=arg_type.arg_names,
                variables=arg_type.variables,
                is_ellipsis_args=arg_type.is_ellipsis_args))
    return ctx.default_return_type


def int_pow_callback(ctx: MethodContext) -> Type:
    """Infer a more precise return type for int.__pow__."""
    # int.__pow__ has an optional modulo argument,
    # so we expect 2 argument positions
    if (len(ctx.arg_types) == 2
            and len(ctx.arg_types[0]) == 1 and len(ctx.arg_types[1]) == 0):
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


def int_neg_callback(ctx: MethodContext) -> Type:
    """Infer a more precise return type for int.__neg__.

    This is mainly used to infer the return type as LiteralType
    if the original underlying object is a LiteralType object
    """
    if isinstance(ctx.type, Instance) and ctx.type.last_known_value is not None:
        value = ctx.type.last_known_value.value
        fallback = ctx.type.last_known_value.fallback
        if isinstance(value, int):
            if is_literal_type_like(ctx.api.type_context[-1]):
                return LiteralType(value=-value, fallback=fallback)
            else:
                return ctx.type.copy_modified(last_known_value=LiteralType(
                    value=-value,
                    fallback=ctx.type,
                    line=ctx.type.line,
                    column=ctx.type.column,
                ))
    elif isinstance(ctx.type, LiteralType):
        value = ctx.type.value
        fallback = ctx.type.fallback
        if isinstance(value, int):
            return LiteralType(value=-value, fallback=fallback)
    return ctx.default_return_type


def tuple_mul_callback(ctx: MethodContext) -> Type:
    """Infer a more precise return type for tuple.__mul__ and tuple.__rmul__.

    This is used to return a specific sized tuple if multiplied by Literal int
    """
    if not isinstance(ctx.type, TupleType):
        return ctx.default_return_type

    arg_type = get_proper_type(ctx.arg_types[0][0])
    if isinstance(arg_type, Instance) and arg_type.last_known_value is not None:
        value = arg_type.last_known_value.value
        if isinstance(value, int):
            return ctx.type.copy_modified(items=ctx.type.items * value)
    elif isinstance(ctx.type, LiteralType):
        value = arg_type.value
        if isinstance(value, int):
            return ctx.type.copy_modified(items=ctx.type.items * value)

    return ctx.default_return_type
