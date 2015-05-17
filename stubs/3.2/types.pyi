# Stubs for types

# TODO this is work in progress

from typing import Any, Undefined

class ModuleType:
    __name__ = Undefined(str)
    __file__ = Undefined(str)
    def __init__(self, name: str, doc: Any) -> None: pass

class MethodType: pass
class BuiltinMethodType: pass

class TracebackType:
    tb_frame = Undefined(Any)
    tb_lasti = Undefined(int)
    tb_lineno = Undefined(int)
    tb_next = Undefined(Any)
