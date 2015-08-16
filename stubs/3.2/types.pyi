# Stubs for types

# TODO this is work in progress

from typing import Any

class ModuleType:
    __name__ = ... # type: str
    __file__ = ... # type: str
    def __init__(self, name: str, doc: Any) -> None: ...

class MethodType: ...
class BuiltinMethodType: ...

class TracebackType:
    tb_frame = ... # type: Any
    tb_lasti = ... # type: int
    tb_lineno = ... # type: int
    tb_next = ... # type: Any
