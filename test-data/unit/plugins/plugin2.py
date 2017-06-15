from mypy.plugin import Plugin

class Plugin2(Plugin):
    def get_function_hook(self, fullname):
        if fullname in ('__main__.f', '__main__.g'):
            return str_hook
        return None

def str_hook(arg_types, args, inferred_return_type, named_generic_type):
    return named_generic_type('builtins.str', [])

def plugin(version):
    return Plugin2
