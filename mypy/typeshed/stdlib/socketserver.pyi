import sys
import types
from _typeshed import Self
from collections.abc import Callable
from socket import socket as _socket
from typing import Any, BinaryIO, ClassVar, Union
from typing_extensions import TypeAlias

__all__ = [
    "BaseServer",
    "TCPServer",
    "UDPServer",
    "ThreadingUDPServer",
    "ThreadingTCPServer",
    "BaseRequestHandler",
    "StreamRequestHandler",
    "DatagramRequestHandler",
    "ThreadingMixIn",
]
if sys.platform != "win32":
    __all__ += [
        "ForkingMixIn",
        "ForkingTCPServer",
        "ForkingUDPServer",
        "ThreadingUnixDatagramServer",
        "ThreadingUnixStreamServer",
        "UnixDatagramServer",
        "UnixStreamServer",
    ]

_RequestType: TypeAlias = Union[_socket, tuple[bytes, _socket]]
_AddressType: TypeAlias = Union[tuple[str, int], str]

# This can possibly be generic at some point:
class BaseServer:
    address_family: int
    server_address: tuple[str, int]
    socket: _socket
    allow_reuse_address: bool
    request_queue_size: int
    socket_type: int
    timeout: float | None
    def __init__(
        self: Self, server_address: Any, RequestHandlerClass: Callable[[Any, Any, Self], BaseRequestHandler]
    ) -> None: ...
    # It is not actually a `@property`, but we need a `Self` type:
    @property
    def RequestHandlerClass(self: Self) -> Callable[[Any, Any, Self], BaseRequestHandler]: ...
    @RequestHandlerClass.setter
    def RequestHandlerClass(self: Self, val: Callable[[Any, Any, Self], BaseRequestHandler]) -> None: ...
    def fileno(self) -> int: ...
    def handle_request(self) -> None: ...
    def serve_forever(self, poll_interval: float = ...) -> None: ...
    def shutdown(self) -> None: ...
    def server_close(self) -> None: ...
    def finish_request(self, request: _RequestType, client_address: _AddressType) -> None: ...
    def get_request(self) -> tuple[Any, Any]: ...
    def handle_error(self, request: _RequestType, client_address: _AddressType) -> None: ...
    def handle_timeout(self) -> None: ...
    def process_request(self, request: _RequestType, client_address: _AddressType) -> None: ...
    def server_activate(self) -> None: ...
    def server_bind(self) -> None: ...
    def verify_request(self, request: _RequestType, client_address: _AddressType) -> bool: ...
    def __enter__(self: Self) -> Self: ...
    def __exit__(
        self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: types.TracebackType | None
    ) -> None: ...
    def service_actions(self) -> None: ...
    def shutdown_request(self, request: _RequestType) -> None: ...  # undocumented
    def close_request(self, request: _RequestType) -> None: ...  # undocumented

class TCPServer(BaseServer):
    allow_reuse_port: bool
    request_queue_size: int
    def __init__(
        self: Self,
        server_address: tuple[str, int],
        RequestHandlerClass: Callable[[Any, Any, Self], BaseRequestHandler],
        bind_and_activate: bool = ...,
    ) -> None: ...
    def get_request(self) -> tuple[_socket, Any]: ...

class UDPServer(BaseServer):
    if sys.version_info >= (3, 11):
        allow_reuse_port: bool
    max_packet_size: ClassVar[int]
    def get_request(self) -> tuple[tuple[bytes, _socket], Any]: ...

if sys.platform != "win32":
    class UnixStreamServer(BaseServer):
        def __init__(
            self: Self,
            server_address: str | bytes,
            RequestHandlerClass: Callable[[Any, Any, Self], BaseRequestHandler],
            bind_and_activate: bool = ...,
        ) -> None: ...

    class UnixDatagramServer(BaseServer):
        def __init__(
            self: Self,
            server_address: str | bytes,
            RequestHandlerClass: Callable[[Any, Any, Self], BaseRequestHandler],
            bind_and_activate: bool = ...,
        ) -> None: ...

if sys.platform != "win32":
    class ForkingMixIn:
        timeout: float | None  # undocumented
        active_children: set[int] | None  # undocumented
        max_children: int  # undocumented
        if sys.version_info >= (3, 7):
            block_on_close: bool
        def collect_children(self, *, blocking: bool = ...) -> None: ...  # undocumented
        def handle_timeout(self) -> None: ...  # undocumented
        def service_actions(self) -> None: ...  # undocumented
        def process_request(self, request: _RequestType, client_address: _AddressType) -> None: ...
        def server_close(self) -> None: ...

class ThreadingMixIn:
    daemon_threads: bool
    if sys.version_info >= (3, 7):
        block_on_close: bool
    def process_request_thread(self, request: _RequestType, client_address: _AddressType) -> None: ...  # undocumented
    def process_request(self, request: _RequestType, client_address: _AddressType) -> None: ...
    def server_close(self) -> None: ...

if sys.platform != "win32":
    class ForkingTCPServer(ForkingMixIn, TCPServer): ...
    class ForkingUDPServer(ForkingMixIn, UDPServer): ...

class ThreadingTCPServer(ThreadingMixIn, TCPServer): ...
class ThreadingUDPServer(ThreadingMixIn, UDPServer): ...

if sys.platform != "win32":
    class ThreadingUnixStreamServer(ThreadingMixIn, UnixStreamServer): ...
    class ThreadingUnixDatagramServer(ThreadingMixIn, UnixDatagramServer): ...

class BaseRequestHandler:
    # Those are technically of types, respectively:
    # * _RequestType
    # * _AddressType
    # But there are some concerns that having unions here would cause
    # too much inconvenience to people using it (see
    # https://github.com/python/typeshed/pull/384#issuecomment-234649696)
    request: Any
    client_address: Any
    server: BaseServer
    def __init__(self, request: _RequestType, client_address: _AddressType, server: BaseServer) -> None: ...
    def setup(self) -> None: ...
    def handle(self) -> None: ...
    def finish(self) -> None: ...

class StreamRequestHandler(BaseRequestHandler):
    rbufsize: ClassVar[int]  # undocumented
    wbufsize: ClassVar[int]  # undocumented
    timeout: ClassVar[float | None]  # undocumented
    disable_nagle_algorithm: ClassVar[bool]  # undocumented
    connection: _socket  # undocumented
    rfile: BinaryIO
    wfile: BinaryIO

class DatagramRequestHandler(BaseRequestHandler):
    packet: _socket  # undocumented
    socket: _socket  # undocumented
    rfile: BinaryIO
    wfile: BinaryIO
