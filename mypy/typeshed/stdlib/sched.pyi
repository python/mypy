import sys
from typing import Any, Callable, NamedTuple

__all__ = ["scheduler"]

if sys.version_info >= (3, 10):
    class Event(NamedTuple):
        time: float
        priority: Any
        sequence: int
        action: Callable[..., Any]
        argument: tuple[Any, ...]
        kwargs: dict[str, Any]

else:
    class Event(NamedTuple):
        time: float
        priority: Any
        action: Callable[..., Any]
        argument: tuple[Any, ...]
        kwargs: dict[str, Any]

class scheduler:
    timefunc: Callable[[], float]
    delayfunc: Callable[[float], object]

    def __init__(self, timefunc: Callable[[], float] = ..., delayfunc: Callable[[float], object] = ...) -> None: ...
    def enterabs(
        self,
        time: float,
        priority: Any,
        action: Callable[..., Any],
        argument: tuple[Any, ...] = ...,
        kwargs: dict[str, Any] = ...,
    ) -> Event: ...
    def enter(
        self,
        delay: float,
        priority: Any,
        action: Callable[..., Any],
        argument: tuple[Any, ...] = ...,
        kwargs: dict[str, Any] = ...,
    ) -> Event: ...
    def run(self, blocking: bool = ...) -> float | None: ...
    def cancel(self, event: Event) -> None: ...
    def empty(self) -> bool: ...
    @property
    def queue(self) -> list[Event]: ...
