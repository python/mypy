from mypy.plugin import CallableType, FunctionSigContext, Plugin


class FunctionSigPlugin(Plugin):
    def get_function_signature_hook(self, fullname):
        if fullname == '__main__.dynamic_signature':
            return my_hook
        return None


def my_hook(ctx: FunctionSigContext) -> CallableType:
    arg1_args = ctx.args[0]
    if len(arg1_args) != 1:
        return ctx.default_signature
    arg1_type = ctx.api.get_expression_type(arg1_args[0])
    return ctx.default_signature.copy_modified(
        arg_types=[arg1_type],
        ret_type=arg1_type,
    )


def plugin(version):
    return FunctionSigPlugin
