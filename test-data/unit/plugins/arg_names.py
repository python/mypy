from typing import Optional, Callable

from mypy.plugin import Plugin, MethodContext, FunctionContext
from mypy.types import Type


class ArgNamesPlugin(Plugin):
    def get_function_hook(self, fullname: str
                          ) -> Optional[Callable[[FunctionContext], Type]]:
        if fullname in {'mod.func', 'mod.func_unfilled', 'mod.func_star_expr',
                        'mod.ClassInit', 'mod.Outer.NestedClassInit'}:
            return extract_classname_and_set_as_return_type_function
        return None

    def get_method_hook(self, fullname: str
                        ) -> Optional[Callable[[MethodContext], Type]]:
        if fullname in {'mod.Class.method', 'mod.Class.myclassmethod', 'mod.Class.mystaticmethod',
                        'mod.ClassUnfilled.method', 'mod.ClassStarExpr.method',
                        'mod.ClassChild.method', 'mod.ClassChild.myclassmethod'}:
            return extract_classname_and_set_as_return_type_method
        return None


def extract_classname_and_set_as_return_type_function(ctx: FunctionContext) -> Type:
    classname = ctx.args[ctx.callee_arg_names.index('classname')][0].value
    return ctx.api.named_generic_type(classname, [])


def extract_classname_and_set_as_return_type_method(ctx: MethodContext) -> Type:
    classname = ctx.args[ctx.callee_arg_names.index('classname')][0].value
    return ctx.api.named_generic_type(classname, [])


def plugin(version):
    return ArgNamesPlugin
