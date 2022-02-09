import sys
from _typeshed import Self, StrOrBytesPath
from types import TracebackType
from typing import (
    IO,
    Any,
    AsyncGenerator,
    AsyncIterator,
    Awaitable,
    Callable,
    ContextManager,
    Generator,
    Generic,
    Iterator,
    Optional,
    Protocol,
    Type,
    TypeVar,
    overload,
)
from typing_extensions import ParamSpec

AbstractContextManager = ContextManager
if sys.version_info >= (3, 7):
    from typing import AsyncContextManager

    AbstractAsyncContextManager = AsyncContextManager

_T = TypeVar("_T")
_T_co = TypeVar("_T_co", covariant=True)
_T_io = TypeVar("_T_io", bound=Optional[IO[str]])
_F = TypeVar("_F", bound=Callable[..., Any])
_P = ParamSpec("_P")

_ExitFunc = Callable[[Optional[Type[BaseException]], Optional[BaseException], Optional[TracebackType]], bool]
_CM_EF = TypeVar("_CM_EF", AbstractContextManager[Any], _ExitFunc)

class ContextDecorator:
    def __call__(self, func: _F) -> _F: ...

class _GeneratorContextManager(AbstractContextManager[_T_co], ContextDecorator, Generic[_T_co]):
    # In Python <= 3.6, __init__ and all instance attributes are defined directly on this class.
    # In Python >= 3.7, __init__ and all instance attributes are inherited from _GeneratorContextManagerBase
    # _GeneratorContextManagerBase is more trouble than it's worth to include in the stub; see #6676
    def __init__(self, func: Callable[..., Iterator[_T_co]], args: tuple[Any, ...], kwds: dict[str, Any]) -> None: ...
    gen: Generator[_T_co, Any, Any]
    func: Callable[..., Generator[_T_co, Any, Any]]
    args: tuple[Any, ...]
    kwds: dict[str, Any]

def contextmanager(func: Callable[_P, Iterator[_T_co]]) -> Callable[_P, _GeneratorContextManager[_T_co]]: ...

if sys.version_info >= (3, 10):
    _AF = TypeVar("_AF", bound=Callable[..., Awaitable[Any]])
    class AsyncContextDecorator:
        def __call__(self, func: _AF) -> _AF: ...
    class _AsyncGeneratorContextManager(AbstractAsyncContextManager[_T_co], AsyncContextDecorator, Generic[_T_co]):
        # __init__ and these attributes are actually defined in the base class _GeneratorContextManagerBase,
        # which is more trouble than it's worth to include in the stub (see #6676)
        def __init__(self, func: Callable[..., AsyncIterator[_T_co]], args: tuple[Any, ...], kwds: dict[str, Any]) -> None: ...
        gen: AsyncGenerator[_T_co, Any]
        func: Callable[..., AsyncGenerator[_T_co, Any]]
        args: tuple[Any, ...]
        kwds: dict[str, Any]

elif sys.version_info >= (3, 7):
    class _AsyncGeneratorContextManager(AbstractAsyncContextManager[_T_co], Generic[_T_co]):
        def __init__(self, func: Callable[..., AsyncIterator[_T_co]], args: tuple[Any, ...], kwds: dict[str, Any]) -> None: ...
        gen: AsyncGenerator[_T_co, Any]
        func: Callable[..., AsyncGenerator[_T_co, Any]]
        args: tuple[Any, ...]
        kwds: dict[str, Any]

if sys.version_info >= (3, 7):
    def asynccontextmanager(func: Callable[_P, AsyncIterator[_T_co]]) -> Callable[_P, _AsyncGeneratorContextManager[_T_co]]: ...

class _SupportsClose(Protocol):
    def close(self) -> object: ...

_SupportsCloseT = TypeVar("_SupportsCloseT", bound=_SupportsClose)

class closing(AbstractContextManager[_SupportsCloseT]):
    def __init__(self, thing: _SupportsCloseT) -> None: ...

if sys.version_info >= (3, 10):
    class _SupportsAclose(Protocol):
        def aclose(self) -> Awaitable[object]: ...
    _SupportsAcloseT = TypeVar("_SupportsAcloseT", bound=_SupportsAclose)
    class aclosing(AbstractAsyncContextManager[_SupportsAcloseT]):
        def __init__(self, thing: _SupportsAcloseT) -> None: ...

class suppress(AbstractContextManager[None]):
    def __init__(self, *exceptions: Type[BaseException]) -> None: ...
    def __exit__(
        self, exctype: Type[BaseException] | None, excinst: BaseException | None, exctb: TracebackType | None
    ) -> bool: ...

class redirect_stdout(AbstractContextManager[_T_io]):
    def __init__(self, new_target: _T_io) -> None: ...

class redirect_stderr(AbstractContextManager[_T_io]):
    def __init__(self, new_target: _T_io) -> None: ...

class ExitStack(AbstractContextManager[ExitStack]):
    def __init__(self) -> None: ...
    def enter_context(self, cm: AbstractContextManager[_T]) -> _T: ...
    def push(self, exit: _CM_EF) -> _CM_EF: ...
    def callback(self, __callback: Callable[..., Any], *args: Any, **kwds: Any) -> Callable[..., Any]: ...
    def pop_all(self: Self) -> Self: ...
    def close(self) -> None: ...
    def __enter__(self: Self) -> Self: ...
    def __exit__(
        self, __exc_type: Type[BaseException] | None, __exc_value: BaseException | None, __traceback: TracebackType | None
    ) -> bool: ...

if sys.version_info >= (3, 7):
    _ExitCoroFunc = Callable[[Optional[Type[BaseException]], Optional[BaseException], Optional[TracebackType]], Awaitable[bool]]
    _CallbackCoroFunc = Callable[..., Awaitable[Any]]
    _ACM_EF = TypeVar("_ACM_EF", AbstractAsyncContextManager[Any], _ExitCoroFunc)
    class AsyncExitStack(AbstractAsyncContextManager[AsyncExitStack]):
        def __init__(self) -> None: ...
        def enter_context(self, cm: AbstractContextManager[_T]) -> _T: ...
        def enter_async_context(self, cm: AbstractAsyncContextManager[_T]) -> Awaitable[_T]: ...
        def push(self, exit: _CM_EF) -> _CM_EF: ...
        def push_async_exit(self, exit: _ACM_EF) -> _ACM_EF: ...
        def callback(self, __callback: Callable[..., Any], *args: Any, **kwds: Any) -> Callable[..., Any]: ...
        def push_async_callback(self, __callback: _CallbackCoroFunc, *args: Any, **kwds: Any) -> _CallbackCoroFunc: ...
        def pop_all(self: Self) -> Self: ...
        def aclose(self) -> Awaitable[None]: ...
        def __aenter__(self: Self) -> Awaitable[Self]: ...
        def __aexit__(
            self, __exc_type: Type[BaseException] | None, __exc_value: BaseException | None, __traceback: TracebackType | None
        ) -> Awaitable[bool]: ...

if sys.version_info >= (3, 10):
    class nullcontext(AbstractContextManager[_T], AbstractAsyncContextManager[_T]):
        enter_result: _T
        @overload
        def __init__(self: nullcontext[None], enter_result: None = ...) -> None: ...
        @overload
        def __init__(self: nullcontext[_T], enter_result: _T) -> None: ...
        def __enter__(self) -> _T: ...
        def __exit__(self, *exctype: Any) -> None: ...
        async def __aenter__(self) -> _T: ...
        async def __aexit__(self, *exctype: Any) -> None: ...

elif sys.version_info >= (3, 7):
    class nullcontext(AbstractContextManager[_T]):
        enter_result: _T
        @overload
        def __init__(self: nullcontext[None], enter_result: None = ...) -> None: ...
        @overload
        def __init__(self: nullcontext[_T], enter_result: _T) -> None: ...
        def __enter__(self) -> _T: ...
        def __exit__(self, *exctype: Any) -> None: ...

if sys.version_info >= (3, 11):
    _T_fd_or_any_path = TypeVar("_T_fd_or_any_path", bound=int | StrOrBytesPath)
    class chdir(AbstractContextManager[None], Generic[_T_fd_or_any_path]):
        path: _T_fd_or_any_path
        def __init__(self, path: _T_fd_or_any_path) -> None: ...
        def __enter__(self) -> None: ...
        def __exit__(self, *excinfo: object) -> None: ...
