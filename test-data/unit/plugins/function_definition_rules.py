from __future__ import annotations

from collections.abc import Callable

from mypy.errorcodes import ErrorCode
from mypy.plugin import (
    FunctionBodyContext,
    FunctionBodyResult,
    FunctionDefContext,
    FunctionDefHookResult,
    Plugin,
)
from mypy.types import AnyType, TypeOfAny, UnionType, get_proper_type


UNION_RETURN = ErrorCode(
    code="union-return",
    description="Disallow union return annotations",
    category="General",
)


def refine_explicit_any_return(ctx: FunctionBodyContext) -> FunctionBodyResult | None:
    inferred = get_proper_type(ctx.inferred_return_type)
    if isinstance(inferred, AnyType):
        return None
    return FunctionBodyResult(refined_return=inferred)


def inspect_function_definition(ctx: FunctionDefContext) -> FunctionDefHookResult | None:
    declared_return = get_proper_type(ctx.declared_signature.ret_type)
    if isinstance(declared_return, UnionType):
        ctx.api.fail(
            "Union return types are not allowed",
            ctx.definition,
            code=UNION_RETURN,
        )
    if (
        isinstance(declared_return, AnyType)
        and declared_return.type_of_any == TypeOfAny.explicit
    ):
        return FunctionDefHookResult(after_body=refine_explicit_any_return)
    return None


class FunctionDefinitionRulesPlugin(Plugin):
    def get_function_def_hook(
        self, fullname: str
    ) -> Callable[[FunctionDefContext], FunctionDefHookResult | None] | None:
        return inspect_function_definition


def plugin(version: str) -> type[FunctionDefinitionRulesPlugin]:
    return FunctionDefinitionRulesPlugin
