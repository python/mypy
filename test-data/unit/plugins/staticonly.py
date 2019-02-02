from mypy.plugin import Plugin

class MyPlugin(Plugin):
    def get_class_decorator_hook(self, fullname):
        if fullname == '__main__.static_only':
            return static_only_hook
        assert fullname is not None
        return None

def static_only_hook(ctx):
    typeinfo = ctx.cls.info
    typeinfo.is_not_instantiatable = True

def plugin(version):
    return MyPlugin
