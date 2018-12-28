from typing import Callable, Optional

from mypy.nodes import NameExpr, CallExpr
from mypy.plugin import MethodContext, Plugin
from mypy.types import Instance, Type

ATTR_FULL_NAME = 'pynamodb.attributes.Attribute'


class PynamodbPlugin(Plugin):
    def get_function_hook(self, fullname: str) -> Optional[Callable[[MethodContext], Type]]:
        return _function_hook_callback


def _function_hook_callback(ctx: MethodContext) -> Type:
    if (
        not isinstance(ctx.default_return_type, Instance) or
        not ctx.default_return_type.type.has_base(ATTR_FULL_NAME) or
        # TODO: any better way to tell apart a construction from other functions?
        not isinstance(ctx.context, CallExpr) or
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


def plugin(version: str):
    return PynamodbPlugin
