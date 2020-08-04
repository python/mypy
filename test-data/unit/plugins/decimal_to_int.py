import builtins
from typing import Optional, Callable

from mypy.plugin import Plugin, AnalyzeTypeContext
from mypy.types import CallableType, Type


class MyPlugin(Plugin):
    def get_type_analyze_hook(self, fullname):
        if fullname == "decimal.Decimal":
            return decorate_hook
        return None

def plugin(version):
    return MyPlugin

def decorate_hook(ctx):
    return ctx.api.named_type('builtins.int', [])
