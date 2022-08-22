from _heapq import *
from _typeshed import SupportsRichComparison
from collections.abc import Callable, Iterable
from typing import Any, TypeVar

__all__ = ["heappush", "heappop", "heapify", "heapreplace", "merge", "nlargest", "nsmallest", "heappushpop"]

_S = TypeVar("_S")

__about__: str

def merge(
    *iterables: Iterable[_S], key: Callable[[_S], SupportsRichComparison] | None = ..., reverse: bool = ...
) -> Iterable[_S]: ...
def nlargest(n: int, iterable: Iterable[_S], key: Callable[[_S], SupportsRichComparison] | None = ...) -> list[_S]: ...
def nsmallest(n: int, iterable: Iterable[_S], key: Callable[[_S], SupportsRichComparison] | None = ...) -> list[_S]: ...
def _heapify_max(__x: list[Any]) -> None: ...  # undocumented
