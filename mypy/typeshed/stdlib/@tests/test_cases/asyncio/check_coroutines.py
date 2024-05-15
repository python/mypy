from __future__ import annotations

from asyncio import iscoroutinefunction
from collections.abc import Awaitable, Callable, Coroutine
from typing import Any
from typing_extensions import assert_type


def test_iscoroutinefunction(
    x: Callable[[str, int], Coroutine[str, int, bytes]],
    y: Callable[[str, int], Awaitable[bytes]],
    z: Callable[[str, int], str | Awaitable[bytes]],
    xx: object,
) -> None:
    if iscoroutinefunction(x):
        assert_type(x, Callable[[str, int], Coroutine[str, int, bytes]])

    if iscoroutinefunction(y):
        assert_type(y, Callable[[str, int], Coroutine[Any, Any, bytes]])

    if iscoroutinefunction(z):
        assert_type(z, Callable[[str, int], Coroutine[Any, Any, Any]])

    if iscoroutinefunction(xx):
        assert_type(xx, Callable[..., Coroutine[Any, Any, Any]])
