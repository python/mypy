import sys
from collections.abc import Sequence

__all__ = ["readmodule", "readmodule_ex", "Class", "Function"]

class Class:
    module: str
    name: str
    super: list[Class | str] | None
    methods: dict[str, int]
    file: int
    lineno: int

    if sys.version_info >= (3, 10):
        end_lineno: int | None

    if sys.version_info >= (3, 7):
        parent: Class | None
        children: dict[str, Class | Function]

    if sys.version_info >= (3, 10):
        def __init__(
            self,
            module: str,
            name: str,
            super_: list[Class | str] | None,
            file: str,
            lineno: int,
            parent: Class | None = ...,
            *,
            end_lineno: int | None = ...,
        ) -> None: ...
    elif sys.version_info >= (3, 7):
        def __init__(
            self, module: str, name: str, super: list[Class | str] | None, file: str, lineno: int, parent: Class | None = ...
        ) -> None: ...
    else:
        def __init__(self, module: str, name: str, super: list[Class | str] | None, file: str, lineno: int) -> None: ...

class Function:
    module: str
    name: str
    file: int
    lineno: int

    if sys.version_info >= (3, 10):
        end_lineno: int | None
        is_async: bool

    if sys.version_info >= (3, 7):
        parent: Function | Class | None
        children: dict[str, Class | Function]

    if sys.version_info >= (3, 10):
        def __init__(
            self,
            module: str,
            name: str,
            file: str,
            lineno: int,
            parent: Function | Class | None = ...,
            is_async: bool = ...,
            *,
            end_lineno: int | None = ...,
        ) -> None: ...
    elif sys.version_info >= (3, 7):
        def __init__(self, module: str, name: str, file: str, lineno: int, parent: Function | Class | None = ...) -> None: ...
    else:
        def __init__(self, module: str, name: str, file: str, lineno: int) -> None: ...

def readmodule(module: str, path: Sequence[str] | None = ...) -> dict[str, Class]: ...
def readmodule_ex(module: str, path: Sequence[str] | None = ...) -> dict[str, Class | Function | list[str]]: ...
