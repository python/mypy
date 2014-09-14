from typing import Any, Function, typevar, Generic, List
from asyncio.events import AbstractEventLoop
# __all__ = ['CancelledError', 'TimeoutError',
#            'InvalidStateError',
#            'Future', 'wrap_future',
#            ]
__all__ = ['Future']

_T = typevar('_T')

class _TracebackLogger:
    __slots__ = [] # type: List[str]
    exc = Any # Exception
    tb = [] # type: List[str]
    def __init__(self, exc: Any, loop: AbstractEventLoop) -> None: pass
    def activate(self) -> None: pass
    def clear(self) -> None: pass
    def __del__(self) -> None: pass

class Future(Generic[_T]):
    _state = ''
    _exception = Any #Exception
    _blocking = False
    _log_traceback = False
    _tb_logger = _TracebackLogger
    def __init__(self, loop: AbstractEventLoop) -> None: pass
    def __repr__(self) -> str: pass
    def __del__(self) -> None: pass
    def cancel(self) -> bool: pass
    def _schedule_callbacks(self) -> None: pass
    def cancelled(self) -> bool: pass
    def done(self) -> bool: pass
    def result(self) -> _T: pass
    def exception(self) -> Any: pass
    def add_done_callback(self, fn: Function[[],Any]) -> None: pass
    def remove_done_callback(self, fn: Function[[], Any]) -> int: pass
    def set_result(self, result: _T) -> None: pass
    def set_exception(self, exception: Any) -> None: pass
    def _copy_state(self, other: Any) -> None: pass
    def __iter__(self) -> Any: pass
