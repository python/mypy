from typing import Callable, Optional, Type

import mypy.types
from mypy.nodes import NameExpr, CallExpr, TypeInfo
from mypy.plugin import Plugin, FunctionContext

ATTR_FULL_NAME = 'pynamodb.attributes.Attribute'


class PynamodbPlugin(Plugin):
    def get_function_hook(self, fullname: str) -> Optional[Callable[[FunctionContext], mypy.types.Type]]:
        return _function_hook_callback


def _function_hook_callback(ctx: FunctionContext) -> mypy.types.Type:
    if (
        not isinstance(ctx.default_return_type, mypy.types.Instance) or
        not ctx.default_return_type.type.has_base(ATTR_FULL_NAME) or
        # TODO: any better way to tell apart a construction from other functions?
        not isinstance(ctx.context, CallExpr) or
        not isinstance(ctx.context.callee, NameExpr) or
        not isinstance(ctx.default_return_type.type, TypeInfo) or
        not ctx.context.callee.fullname == ctx.default_return_type.type.fullname()
    ):
        return ctx.default_return_type

    attr_type = ctx.default_return_type
    base_types = [base for base in attr_type.type.bases
                  if base.type.fullname() == 'pynamodb.attributes.Attribute']
    if not base_types:
        return ctx.default_return_type
    base_type = base_types[0]
    underlying_type = base_type.args[0]

    # If initializer gets named arg null=True,
    # wrap in _NullableAttribute to make the underlying type optional
    for arg_name, arg_expr in zip(ctx.context.arg_names, ctx.context.args):
        if isinstance(arg_expr, NameExpr) and arg_expr.fullname == 'builtins.True':
            return ctx.api.named_generic_type('pynamodb.attributes._NullableAttribute', [
                attr_type,
                underlying_type,
            ])

    return ctx.default_return_type


def plugin(version: str) -> Type[PynamodbPlugin]:
    return PynamodbPlugin
