# This only exists in 3.11+. See VERSIONS.

from _typeshed import Self
from collections.abc import Coroutine, Generator
from contextvars import Context
from types import TracebackType
from typing import Any, TypeVar

from .tasks import Task

__all__ = ["TaskGroup"]

_T = TypeVar("_T")

class TaskGroup:
    async def __aenter__(self: Self) -> Self: ...
    async def __aexit__(self, et: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None) -> None: ...
    def create_task(
        self, coro: Generator[Any, None, _T] | Coroutine[Any, Any, _T], *, name: str | None = None, context: Context | None = None
    ) -> Task[_T]: ...
