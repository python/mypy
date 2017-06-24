from mypy.plugin import Plugin

class Plugin2(Plugin):
    def get_function_hook(self, fullname):
        if fullname in ('__main__.f', '__main__.g'):
            return str_hook
        return None

def str_hook(ctx):
    return ctx.api.named_generic_type('builtins.str', [])

def plugin(version):
    return Plugin2
