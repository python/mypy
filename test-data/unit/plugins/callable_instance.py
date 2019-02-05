from mypy.plugin import MethodContext, Plugin
from mypy.types import Instance, Type

class CallableInstancePlugin(Plugin):
    def get_function_hook(self, fullname):
        assert not fullname.endswith(' of Foo')

    def get_method_hook(self, fullname):
        # Ensure that all names are fully qualified
        assert not fullname.endswith(' of Foo')

        if fullname == '__main__.Class.__call__':
            return my_hook

        return None

def my_hook(ctx: MethodContext) -> Type:
    if isinstance(ctx.type, Instance) and len(ctx.type.args) == 1:
        return ctx.type.args[0]
    return ctx.default_return_type

def plugin(version):
    return CallableInstancePlugin
