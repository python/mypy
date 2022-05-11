import sys
from collections.abc import Awaitable
from typing import TypeVar

__all__ = ("run",)
_T = TypeVar("_T")
if sys.version_info >= (3, 8):
    def run(main: Awaitable[_T], *, debug: bool | None = ...) -> _T: ...

else:
    def run(main: Awaitable[_T], *, debug: bool = ...) -> _T: ...
