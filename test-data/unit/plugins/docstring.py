from mypy.plugin import Plugin
from mypy.fastparse import parse_type_comment

class MyPlugin(Plugin):
    def get_docstring_parser_hook(self):
        return my_hook

def my_hook(ctx):
    params = [l.split(':', 1) for l in ctx.docstring.strip().split('\n')]
    return {k.strip(): parse_type_comment(v.strip(), ctx.line + i + 1, ctx.errors)
            for i, (k, v) in enumerate(params)}

def plugin(version):
    return MyPlugin
