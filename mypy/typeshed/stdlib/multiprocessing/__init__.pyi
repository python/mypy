import sys
from collections.abc import Callable, Iterable
from logging import Logger
from multiprocessing import connection, context, pool, reduction as reducer, synchronize
from multiprocessing.context import (
    AuthenticationError as AuthenticationError,
    BaseContext,
    BufferTooShort as BufferTooShort,
    DefaultContext,
    Process as Process,
    ProcessError as ProcessError,
    SpawnContext,
    TimeoutError as TimeoutError,
)
from multiprocessing.managers import SyncManager
from multiprocessing.process import active_children as active_children, current_process as current_process

# These are technically functions that return instances of these Queue classes.
# Using them as annotations is deprecated. Either use imports from
# multiprocessing.queues or the aliases defined below. See #4266 for discussion.
from multiprocessing.queues import JoinableQueue as JoinableQueue, Queue as Queue, SimpleQueue as SimpleQueue
from multiprocessing.spawn import freeze_support as freeze_support
from typing import Any, TypeVar, overload
from typing_extensions import Literal, TypeAlias

if sys.version_info >= (3, 8):
    from multiprocessing.process import parent_process as parent_process

if sys.platform != "win32":
    from multiprocessing.context import ForkContext, ForkServerContext

if sys.version_info >= (3, 8):
    __all__ = [
        "Array",
        "AuthenticationError",
        "Barrier",
        "BoundedSemaphore",
        "BufferTooShort",
        "Condition",
        "Event",
        "JoinableQueue",
        "Lock",
        "Manager",
        "Pipe",
        "Pool",
        "Process",
        "ProcessError",
        "Queue",
        "RLock",
        "RawArray",
        "RawValue",
        "Semaphore",
        "SimpleQueue",
        "TimeoutError",
        "Value",
        "active_children",
        "allow_connection_pickling",
        "cpu_count",
        "current_process",
        "freeze_support",
        "get_all_start_methods",
        "get_context",
        "get_logger",
        "get_start_method",
        "parent_process",
        "log_to_stderr",
        "reducer",
        "set_executable",
        "set_forkserver_preload",
        "set_start_method",
    ]
else:
    __all__ = [
        "Array",
        "AuthenticationError",
        "Barrier",
        "BoundedSemaphore",
        "BufferTooShort",
        "Condition",
        "Event",
        "JoinableQueue",
        "Lock",
        "Manager",
        "Pipe",
        "Pool",
        "Process",
        "ProcessError",
        "Queue",
        "RLock",
        "RawArray",
        "RawValue",
        "Semaphore",
        "SimpleQueue",
        "TimeoutError",
        "Value",
        "active_children",
        "allow_connection_pickling",
        "cpu_count",
        "current_process",
        "freeze_support",
        "get_all_start_methods",
        "get_context",
        "get_logger",
        "get_start_method",
        "log_to_stderr",
        "reducer",
        "set_executable",
        "set_forkserver_preload",
        "set_start_method",
    ]

# The following type aliases can be used to annotate the return values of
# the corresponding functions. They are not defined at runtime.
#
# from multiprocessing import Lock
# from typing import TYPE_CHECKING
# if TYPE_CHECKING:
#     from multiprocessing import _LockType
# lock: _LockType = Lock()

_T = TypeVar("_T")
_QueueType: TypeAlias = Queue[_T]
_SimpleQueueType: TypeAlias = SimpleQueue[_T]
_JoinableQueueType: TypeAlias = JoinableQueue[_T]
_BarrierType: TypeAlias = synchronize.Barrier
_BoundedSemaphoreType: TypeAlias = synchronize.BoundedSemaphore
_ConditionType: TypeAlias = synchronize.Condition
_EventType: TypeAlias = synchronize.Event
_LockType: TypeAlias = synchronize.Lock
_RLockType: TypeAlias = synchronize.RLock
_SemaphoreType: TypeAlias = synchronize.Semaphore

# N.B. The functions below are generated at runtime by partially applying
# multiprocessing.context.BaseContext's methods, so the two signatures should
# be identical (modulo self).

# Synchronization primitives
_LockLike: TypeAlias = synchronize.Lock | synchronize.RLock
RawValue = context._default_context.RawValue
RawArray = context._default_context.RawArray
Value = context._default_context.Value
Array = context._default_context.Array

def Barrier(parties: int, action: Callable[..., Any] | None = ..., timeout: float | None = ...) -> _BarrierType: ...
def BoundedSemaphore(value: int = ...) -> _BoundedSemaphoreType: ...
def Condition(lock: _LockLike | None = ...) -> _ConditionType: ...
def Event() -> _EventType: ...
def Lock() -> _LockType: ...
def RLock() -> _RLockType: ...
def Semaphore(value: int = ...) -> _SemaphoreType: ...
def Pipe(duplex: bool = ...) -> tuple[connection.Connection, connection.Connection]: ...
def Pool(
    processes: int | None = ...,
    initializer: Callable[..., Any] | None = ...,
    initargs: Iterable[Any] = ...,
    maxtasksperchild: int | None = ...,
) -> pool.Pool: ...

# ----- multiprocessing function stubs -----
def allow_connection_pickling() -> None: ...
def cpu_count() -> int: ...
def get_logger() -> Logger: ...
def log_to_stderr(level: str | int | None = ...) -> Logger: ...
def Manager() -> SyncManager: ...
def set_executable(executable: str) -> None: ...
def set_forkserver_preload(module_names: list[str]) -> None: ...
def get_all_start_methods() -> list[str]: ...
def get_start_method(allow_none: bool = ...) -> str | None: ...
def set_start_method(method: str, force: bool | None = ...) -> None: ...

if sys.platform != "win32":
    @overload
    def get_context(method: None = ...) -> DefaultContext: ...
    @overload
    def get_context(method: Literal["spawn"]) -> SpawnContext: ...
    @overload
    def get_context(method: Literal["fork"]) -> ForkContext: ...
    @overload
    def get_context(method: Literal["forkserver"]) -> ForkServerContext: ...
    @overload
    def get_context(method: str) -> BaseContext: ...

else:
    @overload
    def get_context(method: None = ...) -> DefaultContext: ...
    @overload
    def get_context(method: Literal["spawn"]) -> SpawnContext: ...
    @overload
    def get_context(method: str) -> BaseContext: ...
