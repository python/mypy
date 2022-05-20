import pickle
import sys
from abc import ABCMeta
from copyreg import _DispatchTableType
from typing import Any
from typing_extensions import Literal

if sys.platform == "win32":
    __all__ = ["send_handle", "recv_handle", "ForkingPickler", "register", "dump", "DupHandle", "duplicate", "steal_handle"]
else:
    __all__ = ["send_handle", "recv_handle", "ForkingPickler", "register", "dump", "DupFd", "sendfds", "recvfds"]

class ForkingPickler(pickle.Pickler):
    dispatch_table: _DispatchTableType
    def __init__(self, *args) -> None: ...
    @classmethod
    def register(cls, type, reduce) -> None: ...
    @classmethod
    def dumps(cls, obj, protocol: Any | None = ...): ...
    loads = pickle.loads

register = ForkingPickler.register

def dump(obj, file, protocol: Any | None = ...) -> None: ...

if sys.platform == "win32":
    if sys.version_info >= (3, 8):
        def duplicate(handle, target_process: Any | None = ..., inheritable: bool = ..., *, source_process: Any | None = ...): ...
    else:
        def duplicate(handle, target_process: Any | None = ..., inheritable: bool = ...): ...

    def steal_handle(source_pid, handle): ...
    def send_handle(conn, handle, destination_pid) -> None: ...
    def recv_handle(conn): ...

    class DupHandle:
        def __init__(self, handle, access, pid: Any | None = ...) -> None: ...
        def detach(self): ...

else:
    if sys.platform == "darwin":
        ACKNOWLEDGE: Literal[True]
    else:
        ACKNOWLEDGE: Literal[False]

    def recvfds(sock, size): ...
    def send_handle(conn, handle, destination_pid) -> None: ...
    def recv_handle(conn) -> None: ...
    def sendfds(sock, fds) -> None: ...
    def DupFd(fd): ...

# These aliases are to work around pyright complaints.
# Pyright doesn't like it when a class object is defined as an alias
# of a global object with the same name.
_ForkingPickler = ForkingPickler
_register = register
_dump = dump
_send_handle = send_handle
_recv_handle = recv_handle

if sys.platform == "win32":
    _steal_handle = steal_handle
    _duplicate = duplicate
    _DupHandle = DupHandle
else:
    _sendfds = sendfds
    _recvfds = recvfds
    _DupFd = DupFd

class AbstractReducer(metaclass=ABCMeta):
    ForkingPickler = _ForkingPickler
    register = _register
    dump = _dump
    send_handle = _send_handle
    recv_handle = _recv_handle
    if sys.platform == "win32":
        steal_handle = _steal_handle
        duplicate = _duplicate
        DupHandle = _DupHandle
    else:
        sendfds = _sendfds
        recvfds = _recvfds
        DupFd = _DupFd
    def __init__(self, *args) -> None: ...
