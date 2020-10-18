from mypy.plugin import Plugin

class DummyPlugin(Plugin):
    def get_customize_class_mro_hook(self, fullname):
        def analyze(classdef_ctx):
            pass
        return analyze

def plugin(version):
    return DummyPlugin
