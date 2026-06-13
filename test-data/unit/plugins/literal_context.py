from collections.abc import Callable

from mypy.plugin import FunctionContext, Plugin
from mypy.types import Type


class LiteralContextPlugin(Plugin):
    def get_function_hook(self, fullname: str) -> Callable[[FunctionContext], Type] | None:
        if fullname == "__main__.print_literal_context":
            return report_literal_type_context
        return None


def report_literal_type_context(ctx: FunctionContext) -> Type:
    typ = ctx.arg_types[0][0]
    ctx.api.msg.note(f"literal type {typ} has line and column context", typ)
    return ctx.default_return_type


def plugin(version: str) -> type[LiteralContextPlugin]:
    return LiteralContextPlugin
