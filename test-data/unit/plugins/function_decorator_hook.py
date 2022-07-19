from mypy.plugin import Plugin, FunctionDecoratorContext


class FunctionDecoratorPlugin(Plugin):
    def get_function_decorator_hook(self, fullname):
        if fullname == 'm.decorator':
            return my_hook
        return None


def my_hook(ctx: FunctionDecoratorContext) -> bool:
    ctx.decorated_function.func.is_property = True
    ctx.decorated_function.var.is_property = True

    return True


def plugin(version):
    return FunctionDecoratorPlugin
