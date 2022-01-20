from typing import Any, Awaitable, Callable, Iterable

from . import events

async def staggered_race(
    coro_fns: Iterable[Callable[[], Awaitable[Any]]], delay: float | None, *, loop: events.AbstractEventLoop | None = ...
) -> tuple[Any, int | None, list[Exception | None]]: ...
