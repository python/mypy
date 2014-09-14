from typing import Any, typevar, List, Function, Tuple, Union, Dict
from abc import ABCMeta, abstractmethod
from asyncio.futures import Future
import socket, subprocess

# __all__ = ['AbstractEventLoopPolicy',
#            'AbstractEventLoop', 'AbstractServer',
#            'Handle', 'TimerHandle',
#            'get_event_loop_policy', 'set_event_loop_policy',
#            'get_event_loop', 'set_event_loop', 'new_event_loop',
#            'get_child_watcher', 'set_child_watcher',
#            ]


__all__ = ['AbstractEventLoop', 'Handle', 'get_event_loop']

_T = typevar('_T')

class Handle:
    __slots__ = [] # type: List[str]
    _cancelled = False
    _args = [] # type: List[Any]
    def __init__(self, callback: Function[[],Any], args: List[Any],
        loop: AbstractEventLoop) -> None: pass
    def __repr__(self) -> str: pass
    def cancel(self) -> None: pass
    def _run(self) -> None: pass


class AbstractEventLoop(metaclass=ABCMeta):
    @abstractmethod
    def run_forever(self) -> None: pass
    @abstractmethod
    def run_until_complete(self, future: Future[_T]) -> _T: pass
    @abstractmethod
    def stop(self) -> None: pass
    @abstractmethod
    def is_running(self) -> bool: pass
    @abstractmethod
    def close(self) -> None: pass
    # Methods scheduling callbacks.  All these return Handles.
    @abstractmethod
    def call_soon(self, callback: Function[[],Any], *args: Any) -> Handle: pass
    @abstractmethod
    def call_later(self, delay: Union[int, float], callback: Function[[],Any], *args: Any) -> Handle: pass
    @abstractmethod
    def call_at(self, when: float, callback: Function[[],Any], *args: Any) -> Handle: pass
    @abstractmethod
    def time(self) -> float: pass
    # Methods for interacting with threads
    @abstractmethod
    def call_soon_threadsafe(self, callback: Function[[],Any], *args: Any) -> Handle: pass
    @abstractmethod
    def run_in_executor(self, executor: Any,
        callback: Function[[],Any], *args: Any) -> Future[Any]: pass
    @abstractmethod
    def set_default_executor(self, executor: Any) -> None: pass
    # Network I/O methods returning Futures.
    @abstractmethod
    def getaddrinfo(self, host: str, port: int, *,
        family: int=0, type: int=0, proto: int=0, flags: int=0) -> List[Tuple[int, int, int, str, tuple]]: pass
    @abstractmethod
    def getnameinfo(self, sockaddr: tuple, flags: int=0) -> Tuple[str, int]: pass
    @abstractmethod
    def create_connection(self, protocol_factory: Any, host: str=None, port: int=None, *,
                          ssl: Any=None, family: int=0, proto: int=0, flags: int=0, sock: Any=None,
                          local_addr: str=None, server_hostname: str=None) -> tuple: pass
                          # ?? check Any
                          # return (Transport, Protocol)
    @abstractmethod
    def create_server(self, protocol_factory: Any, host: str=None, port: int=None, *,
                      family: int=socket.AF_UNSPEC, flags: int=socket.AI_PASSIVE,
                      sock: Any=None, backlog: int=100, ssl: Any=None, reuse_address: Any=None) -> Any: pass
                    # ?? check Any
                    # return Server
    @abstractmethod
    def create_unix_connection(self, protocol_factory: Any, path: str, *,
                               ssl: Any=None, sock: Any=None,
                               server_hostname: str=None) -> tuple: pass
                    # ?? check Any
                    # return tuple(Transport, Protocol)
    @abstractmethod
    def create_unix_server(self, protocol_factory: Any, path: str, *,
                           sock: Any=None, backlog: int=100, ssl: Any=None) -> Any: pass
                    # ?? check Any
                    # return Server
    @abstractmethod
    def create_datagram_endpoint(self, protocol_factory: Any,
                                 local_addr: str=None, remote_addr: str=None, *,
                                 family: int=0, proto: int=0, flags: int=0) -> tuple: pass
                    #?? check Any
                    # return (Transport, Protocol)
    # Pipes and subprocesses.
    @abstractmethod
    def connect_read_pipe(self, protocol_factory: Any, pipe: Any) -> tuple: pass
                    #?? check Any
                    # return (Transport, Protocol)
    @abstractmethod
    def connect_write_pipe(self, protocol_factory: Any, pipe: Any) -> tuple: pass
                    #?? check Any
                    # return (Transport, Protocol)
    @abstractmethod
    def subprocess_shell(self, protocol_factory: Any, cmd: Union[bytes,str], *, stdin: Any=subprocess.PIPE,
                         stdout: Any=subprocess.PIPE, stderr: Any=subprocess.PIPE,
                         **kwargs: Dict[str, Any]) -> tuple: pass
                    #?? check Any
                    # return (Transport, Protocol)
    @abstractmethod
    def subprocess_exec(self, protocol_factory: Any, *args: List[Any], stdin: Any=subprocess.PIPE,
                        stdout: Any=subprocess.PIPE, stderr: Any=subprocess.PIPE,
                        **kwargs: Dict[str, Any]) -> tuple: pass
                    #?? check Any
                    # return (Transport, Protocol)
    @abstractmethod
    def add_reader(self, fd: int, callback: Function[[],Any], *args: List[Any]) -> None: pass
    @abstractmethod
    def remove_reader(self, fd: int) -> None: pass
    @abstractmethod
    def add_writer(self, fd: int, callback: Function[[],Any], *args: List[Any]) -> None: pass
    @abstractmethod
    def remove_writer(self, fd: int) -> None: pass
    # Completion based I/O methods returning Futures.
    @abstractmethod
    def sock_recv(self, sock: Any, nbytes: int) -> Any: pass #TODO
    @abstractmethod
    def sock_sendall(self, sock: Any, data: bytes) -> None: pass #TODO
    @abstractmethod
    def sock_connect(self, sock: Any, address: str) -> Any: pass #TODO
    @abstractmethod
    def sock_accept(self, sock: Any) -> Any: pass
    # Signal handling.
    @abstractmethod
    def add_signal_handler(self, sig: int, callback: Function[[],Any], *args: List[Any]) -> None: pass
    @abstractmethod
    def remove_signal_handler(self, sig: int) -> None: pass
    # Error handlers.
    @abstractmethod
    def set_exception_handler(self, handler: Function[[], Any]) -> None: pass
    @abstractmethod
    def default_exception_handler(self, context: Any) -> None: pass
    @abstractmethod
    def call_exception_handler(self, context: Any) -> None: pass
    # Debug flag management.
    @abstractmethod
    def get_debug(self) -> bool: pass
    @abstractmethod
    def set_debug(self, enabled: bool) -> None: pass


def get_event_loop() -> AbstractEventLoop: pass
