import sys
from contextvars import Context
from types import TracebackType
from typing import TypeVar
from typing_extensions import Self

from . import _CoroutineLike
from .tasks import Task

if sys.version_info >= (3, 12):
    __all__ = ("TaskGroup",)
else:
    __all__ = ["TaskGroup"]

_T = TypeVar("_T")

class TaskGroup:
    async def __aenter__(self) -> Self: ...
    async def __aexit__(self, et: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None) -> None: ...
    def create_task(self, coro: _CoroutineLike[_T], *, name: str | None = None, context: Context | None = None) -> Task[_T]: ...
