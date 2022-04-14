import sys
from typing import Any, Callable, Sequence
from typing_extensions import Literal

if sys.version_info >= (3, 7):
    from contextvars import Context

from . import futures

if sys.version_info >= (3, 7):
    __all__ = ()
else:
    __all__: list[str] = []

# asyncio defines 'isfuture()' in base_futures.py and re-imports it in futures.py
# but it leads to circular import error in pytype tool.
# That's why the import order is reversed.
from .futures import isfuture as isfuture

_PENDING: Literal["PENDING"]  # undocumented
_CANCELLED: Literal["CANCELLED"]  # undocumented
_FINISHED: Literal["FINISHED"]  # undocumented

if sys.version_info >= (3, 7):
    def _format_callbacks(cb: Sequence[tuple[Callable[[futures.Future[Any]], None], Context]]) -> str: ...  # undocumented

else:
    def _format_callbacks(cb: Sequence[Callable[[futures.Future[Any]], None]]) -> str: ...  # undocumented

def _future_repr_info(future: futures.Future[Any]) -> list[str]: ...  # undocumented
