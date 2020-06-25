import sys
from ._base import (
    FIRST_COMPLETED as FIRST_COMPLETED,
    FIRST_EXCEPTION as FIRST_EXCEPTION,
    ALL_COMPLETED as ALL_COMPLETED,
    CancelledError as CancelledError,
    TimeoutError as TimeoutError,
    Future as Future,
    Executor as Executor,
    wait as wait,
    as_completed as as_completed,
)
if sys.version_info >= (3, 8):
    from ._base import InvalidStateError as InvalidStateError
if sys.version_info >= (3, 7):
    from ._base import BrokenExecutor as BrokenExecutor
from .thread import ThreadPoolExecutor as ThreadPoolExecutor
from .process import ProcessPoolExecutor as ProcessPoolExecutor
