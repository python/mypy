from mypy.errorcodes import ErrorCode
from mypy.plugin import Plugin
from mypy.types import AnyType, TypeOfAny

CUSTOM_ERROR = ErrorCode(code="custom", description="", category="Custom")


class CustomErrorCodePlugin(Plugin):
    def get_function_hook(self, fullname):
        if fullname.endswith(".main"):
            return self.emit_error
        return None

    def emit_error(self, ctx):
        ctx.api.fail("Custom error", ctx.context, code=CUSTOM_ERROR)
        return AnyType(TypeOfAny.from_error)


def plugin(version):
    return CustomErrorCodePlugin
