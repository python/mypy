# Stubs for types

# TODO this is work in progress

from typing import Any, Undefined

class ModuleType:
    __name__ = Undefined(str)
    __file__ = Undefined(str)
    def __init__(self, name: str, doc: Any) -> None: pass

class MethodType: pass
class BuiltinMethodType: pass
