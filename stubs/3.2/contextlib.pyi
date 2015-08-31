# Stubs for contextlib

# NOTE: These are incomplete!

from typing import Any, TypeVar, Generic

# TODO more precise type?
def contextmanager(func: Any) -> Any: ...

_T = TypeVar('_T')

class closing(Generic[_T]):
    def __init__(self, thing: _T) -> None: ...
    def __enter__(self) -> _T: ...
    def __exit__(self, *exc_info) -> None: ...
