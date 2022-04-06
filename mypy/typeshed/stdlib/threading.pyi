import sys
from types import FrameType, TracebackType
from typing import Any, Callable, Iterable, Mapping, TypeVar

# TODO recursive type
_TF = Callable[[FrameType, str, Any], Callable[..., Any] | None]

_PF = Callable[[FrameType, str, Any], None]
_T = TypeVar("_T")

if sys.version_info >= (3, 10):
    __all__ = [
        "get_ident",
        "active_count",
        "Condition",
        "current_thread",
        "enumerate",
        "main_thread",
        "TIMEOUT_MAX",
        "Event",
        "Lock",
        "RLock",
        "Semaphore",
        "BoundedSemaphore",
        "Thread",
        "Barrier",
        "BrokenBarrierError",
        "Timer",
        "ThreadError",
        "setprofile",
        "settrace",
        "local",
        "stack_size",
        "excepthook",
        "ExceptHookArgs",
        "gettrace",
        "getprofile",
        "get_native_id",
    ]
elif sys.version_info >= (3, 8):
    __all__ = [
        "get_ident",
        "active_count",
        "Condition",
        "current_thread",
        "enumerate",
        "main_thread",
        "TIMEOUT_MAX",
        "Event",
        "Lock",
        "RLock",
        "Semaphore",
        "BoundedSemaphore",
        "Thread",
        "Barrier",
        "BrokenBarrierError",
        "Timer",
        "ThreadError",
        "setprofile",
        "settrace",
        "local",
        "stack_size",
        "excepthook",
        "ExceptHookArgs",
        "get_native_id",
    ]
else:
    __all__ = [
        "get_ident",
        "active_count",
        "Condition",
        "current_thread",
        "enumerate",
        "main_thread",
        "TIMEOUT_MAX",
        "Event",
        "Lock",
        "RLock",
        "Semaphore",
        "BoundedSemaphore",
        "Thread",
        "Barrier",
        "BrokenBarrierError",
        "Timer",
        "ThreadError",
        "setprofile",
        "settrace",
        "local",
        "stack_size",
    ]

_profile_hook: _PF | None

def active_count() -> int: ...
def activeCount() -> int: ...  # deprecated alias for active_count()
def current_thread() -> Thread: ...
def currentThread() -> Thread: ...  # deprecated alias for current_thread()
def get_ident() -> int: ...
def enumerate() -> list[Thread]: ...
def main_thread() -> Thread: ...

if sys.version_info >= (3, 8):
    from _thread import get_native_id as get_native_id

def settrace(func: _TF) -> None: ...
def setprofile(func: _PF | None) -> None: ...

if sys.version_info >= (3, 10):
    def gettrace() -> _TF | None: ...
    def getprofile() -> _PF | None: ...

def stack_size(size: int = ...) -> int: ...

TIMEOUT_MAX: float

class ThreadError(Exception): ...

class local:
    def __getattribute__(self, __name: str) -> Any: ...
    def __setattr__(self, __name: str, __value: Any) -> None: ...
    def __delattr__(self, __name: str) -> None: ...

class Thread:
    name: str
    @property
    def ident(self) -> int | None: ...
    daemon: bool
    def __init__(
        self,
        group: None = ...,
        target: Callable[..., Any] | None = ...,
        name: str | None = ...,
        args: Iterable[Any] = ...,
        kwargs: Mapping[str, Any] | None = ...,
        *,
        daemon: bool | None = ...,
    ) -> None: ...
    def start(self) -> None: ...
    def run(self) -> None: ...
    def join(self, timeout: float | None = ...) -> None: ...
    if sys.version_info >= (3, 8):
        @property
        def native_id(self) -> int | None: ...  # only available on some platforms

    def is_alive(self) -> bool: ...
    if sys.version_info < (3, 9):
        def isAlive(self) -> bool: ...
    # the following methods are all deprecated
    def getName(self) -> str: ...
    def setName(self, name: str) -> None: ...
    def isDaemon(self) -> bool: ...
    def setDaemon(self, daemonic: bool) -> None: ...

class _DummyThread(Thread):
    def __init__(self) -> None: ...

class Lock:
    def __init__(self) -> None: ...
    def __enter__(self) -> bool: ...
    def __exit__(
        self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: TracebackType | None
    ) -> bool | None: ...
    def acquire(self, blocking: bool = ..., timeout: float = ...) -> bool: ...
    def release(self) -> None: ...
    def locked(self) -> bool: ...

class _RLock:
    def __init__(self) -> None: ...
    def acquire(self, blocking: bool = ..., timeout: float = ...) -> bool: ...
    def release(self) -> None: ...
    __enter__ = acquire
    def __exit__(self, t: type[BaseException] | None, v: BaseException | None, tb: TracebackType | None) -> None: ...

RLock = _RLock

class Condition:
    def __init__(self, lock: Lock | _RLock | None = ...) -> None: ...
    def __enter__(self) -> bool: ...
    def __exit__(
        self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: TracebackType | None
    ) -> bool | None: ...
    def acquire(self, blocking: bool = ..., timeout: float = ...) -> bool: ...
    def release(self) -> None: ...
    def wait(self, timeout: float | None = ...) -> bool: ...
    def wait_for(self, predicate: Callable[[], _T], timeout: float | None = ...) -> _T: ...
    def notify(self, n: int = ...) -> None: ...
    def notify_all(self) -> None: ...
    def notifyAll(self) -> None: ...  # deprecated alias for notify_all()

class Semaphore:
    def __init__(self, value: int = ...) -> None: ...
    def __exit__(self, t: type[BaseException] | None, v: BaseException | None, tb: TracebackType | None) -> None: ...
    def acquire(self, blocking: bool = ..., timeout: float | None = ...) -> bool: ...
    def __enter__(self, blocking: bool = ..., timeout: float | None = ...) -> bool: ...
    if sys.version_info >= (3, 9):
        def release(self, n: int = ...) -> None: ...
    else:
        def release(self) -> None: ...

class BoundedSemaphore(Semaphore): ...

class Event:
    def __init__(self) -> None: ...
    def is_set(self) -> bool: ...
    def isSet(self) -> bool: ...  # deprecated alias for is_set()
    def set(self) -> None: ...
    def clear(self) -> None: ...
    def wait(self, timeout: float | None = ...) -> bool: ...

if sys.version_info >= (3, 8):
    from _thread import _excepthook, _ExceptHookArgs

    excepthook = _excepthook
    ExceptHookArgs = _ExceptHookArgs

class Timer(Thread):
    def __init__(
        self,
        interval: float,
        function: Callable[..., Any],
        args: Iterable[Any] | None = ...,
        kwargs: Mapping[str, Any] | None = ...,
    ) -> None: ...
    def cancel(self) -> None: ...

class Barrier:
    @property
    def parties(self) -> int: ...
    @property
    def n_waiting(self) -> int: ...
    @property
    def broken(self) -> bool: ...
    def __init__(self, parties: int, action: Callable[[], None] | None = ..., timeout: float | None = ...) -> None: ...
    def wait(self, timeout: float | None = ...) -> int: ...
    def reset(self) -> None: ...
    def abort(self) -> None: ...

class BrokenBarrierError(RuntimeError): ...
