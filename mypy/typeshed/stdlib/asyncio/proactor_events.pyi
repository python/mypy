import sys
from collections.abc import Mapping
from socket import socket
from typing import Any, Protocol
from typing_extensions import Literal

from . import base_events, constants, events, futures, streams, transports

if sys.version_info >= (3, 7):
    __all__ = ("BaseProactorEventLoop",)
else:
    __all__ = ["BaseProactorEventLoop"]

if sys.version_info >= (3, 8):
    class _WarnCallbackProtocol(Protocol):
        def __call__(
            self, message: str, category: type[Warning] | None = ..., stacklevel: int = ..., source: Any | None = ...
        ) -> None: ...

class _ProactorBasePipeTransport(transports._FlowControlMixin, transports.BaseTransport):
    def __init__(
        self,
        loop: events.AbstractEventLoop,
        sock: socket,
        protocol: streams.StreamReaderProtocol,
        waiter: futures.Future[Any] | None = ...,
        extra: Mapping[Any, Any] | None = ...,
        server: events.AbstractServer | None = ...,
    ) -> None: ...
    if sys.version_info >= (3, 8):
        def __del__(self, _warn: _WarnCallbackProtocol = ...) -> None: ...
    else:
        def __del__(self) -> None: ...

    def get_write_buffer_size(self) -> int: ...

class _ProactorReadPipeTransport(_ProactorBasePipeTransport, transports.ReadTransport):
    if sys.version_info >= (3, 10):
        def __init__(
            self,
            loop: events.AbstractEventLoop,
            sock: socket,
            protocol: streams.StreamReaderProtocol,
            waiter: futures.Future[Any] | None = ...,
            extra: Mapping[Any, Any] | None = ...,
            server: events.AbstractServer | None = ...,
            buffer_size: int = ...,
        ) -> None: ...
    else:
        def __init__(
            self,
            loop: events.AbstractEventLoop,
            sock: socket,
            protocol: streams.StreamReaderProtocol,
            waiter: futures.Future[Any] | None = ...,
            extra: Mapping[Any, Any] | None = ...,
            server: events.AbstractServer | None = ...,
        ) -> None: ...

class _ProactorBaseWritePipeTransport(_ProactorBasePipeTransport, transports.WriteTransport):
    def __init__(
        self,
        loop: events.AbstractEventLoop,
        sock: socket,
        protocol: streams.StreamReaderProtocol,
        waiter: futures.Future[Any] | None = ...,
        extra: Mapping[Any, Any] | None = ...,
        server: events.AbstractServer | None = ...,
    ) -> None: ...

class _ProactorWritePipeTransport(_ProactorBaseWritePipeTransport):
    def __init__(
        self,
        loop: events.AbstractEventLoop,
        sock: socket,
        protocol: streams.StreamReaderProtocol,
        waiter: futures.Future[Any] | None = ...,
        extra: Mapping[Any, Any] | None = ...,
        server: events.AbstractServer | None = ...,
    ) -> None: ...

class _ProactorDuplexPipeTransport(_ProactorReadPipeTransport, _ProactorBaseWritePipeTransport, transports.Transport): ...

class _ProactorSocketTransport(_ProactorReadPipeTransport, _ProactorBaseWritePipeTransport, transports.Transport):

    _sendfile_compatible: constants._SendfileMode
    def __init__(
        self,
        loop: events.AbstractEventLoop,
        sock: socket,
        protocol: streams.StreamReaderProtocol,
        waiter: futures.Future[Any] | None = ...,
        extra: Mapping[Any, Any] | None = ...,
        server: events.AbstractServer | None = ...,
    ) -> None: ...
    def _set_extra(self, sock: socket) -> None: ...
    def can_write_eof(self) -> Literal[True]: ...
    def write_eof(self) -> None: ...

class BaseProactorEventLoop(base_events.BaseEventLoop):
    def __init__(self, proactor: Any) -> None: ...
