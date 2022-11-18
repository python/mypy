from mypy.plugin import Plugin
from mypy.plugins.attrs import (
    attr_attrib_makers,
    attr_class_makers,
    attr_dataclass_makers,
)

# See https://www.attrs.org/en/stable/extending.html#mypy for background.
attr_dataclass_makers.add("__main__.my_attr_dataclass")
attr_class_makers.add("__main__.my_attr_s")
attr_attrib_makers.add("__main__.my_attr_ib")


class MyPlugin(Plugin):
    # Our plugin does nothing but it has to exist so this file gets loaded.
    pass


def plugin(version):
    return MyPlugin
