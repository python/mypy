import sys
import types
from _typeshed import Self
from socket import socket
from typing import Any, Callable, Optional, Type

from .base_events import Server
from .events import AbstractEventLoop, BaseDefaultEventLoopPolicy, _ProtocolFactory, _SSLContext
from .selector_events import BaseSelectorEventLoop

class AbstractChildWatcher:
    def add_child_handler(self, pid: int, callback: Callable[..., Any], *args: Any) -> None: ...
    def remove_child_handler(self, pid: int) -> bool: ...
    def attach_loop(self, loop: Optional[AbstractEventLoop]) -> None: ...
    def close(self) -> None: ...
    def __enter__(self: Self) -> Self: ...
    def __exit__(
        self, typ: Optional[Type[BaseException]], exc: Optional[BaseException], tb: Optional[types.TracebackType]
    ) -> None: ...
    if sys.version_info >= (3, 8):
        def is_active(self) -> bool: ...

class BaseChildWatcher(AbstractChildWatcher):
    def __init__(self) -> None: ...

class SafeChildWatcher(BaseChildWatcher):
    def __enter__(self: Self) -> Self: ...

class FastChildWatcher(BaseChildWatcher):
    def __enter__(self: Self) -> Self: ...

class _UnixSelectorEventLoop(BaseSelectorEventLoop):
    if sys.version_info < (3, 7):
        async def create_unix_server(
            self,
            protocol_factory: _ProtocolFactory,
            path: Optional[str] = ...,
            *,
            sock: Optional[socket] = ...,
            backlog: int = ...,
            ssl: _SSLContext = ...,
        ) -> Server: ...

class _UnixDefaultEventLoopPolicy(BaseDefaultEventLoopPolicy):
    def get_child_watcher(self) -> AbstractChildWatcher: ...
    def set_child_watcher(self, watcher: Optional[AbstractChildWatcher]) -> None: ...

SelectorEventLoop = _UnixSelectorEventLoop

DefaultEventLoopPolicy = _UnixDefaultEventLoopPolicy

if sys.version_info >= (3, 8):

    from typing import Protocol
    class _Warn(Protocol):
        def __call__(
            self, message: str, category: Optional[Type[Warning]] = ..., stacklevel: int = ..., source: Optional[Any] = ...
        ) -> None: ...
    class MultiLoopChildWatcher(AbstractChildWatcher):
        def __enter__(self: Self) -> Self: ...
    class ThreadedChildWatcher(AbstractChildWatcher):
        def __enter__(self: Self) -> Self: ...
        def __del__(self, _warn: _Warn = ...) -> None: ...
