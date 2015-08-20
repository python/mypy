# Stubs for types

from typing import Any

class ModuleType:
    __name__ = ... # type: str
    __file__ = ... # type: str
    def __init__(self, name: str, doc: Any) -> None: ...

class TracebackType:
    ...

class FrameType:
    ...

class GeneratorType:
    ...

class ListType:
    ...
