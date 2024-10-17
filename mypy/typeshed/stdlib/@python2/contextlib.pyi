from types import TracebackType
from typing import IO, Any, Callable, ContextManager, Iterable, Iterator, Protocol, TypeVar
from typing_extensions import ParamSpec

_T = TypeVar("_T")
_T_co = TypeVar("_T_co", covariant=True)
_F = TypeVar("_F", bound=Callable[..., Any])
_P = ParamSpec("_P")

_ExitFunc = Callable[[type[BaseException] | None, BaseException | None, TracebackType | None], bool]

class GeneratorContextManager(ContextManager[_T_co]):
    def __call__(self, func: _F) -> _F: ...

def contextmanager(func: Callable[_P, Iterator[_T]]) -> Callable[_P, ContextManager[_T]]: ...
def nested(*mgr: ContextManager[Any]) -> ContextManager[Iterable[Any]]: ...

class _SupportsClose(Protocol):
    def close(self) -> None: ...

_SupportsCloseT = TypeVar("_SupportsCloseT", bound=_SupportsClose)

class closing(ContextManager[_SupportsCloseT]):
    def __init__(self, thing: _SupportsCloseT) -> None: ...
