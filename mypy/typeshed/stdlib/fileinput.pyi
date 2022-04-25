import sys
from _typeshed import Self, StrOrBytesPath
from collections.abc import Callable, Iterable, Iterator
from types import TracebackType
from typing import IO, Any, AnyStr, Generic

__all__ = [
    "input",
    "close",
    "nextfile",
    "filename",
    "lineno",
    "filelineno",
    "fileno",
    "isfirstline",
    "isstdin",
    "FileInput",
    "hook_compressed",
    "hook_encoded",
]

if sys.version_info >= (3, 9):
    from types import GenericAlias

if sys.version_info >= (3, 10):
    def input(
        files: StrOrBytesPath | Iterable[StrOrBytesPath] | None = ...,
        inplace: bool = ...,
        backup: str = ...,
        *,
        mode: str = ...,
        openhook: Callable[[StrOrBytesPath, str], IO[AnyStr]] = ...,
        encoding: str | None = ...,
        errors: str | None = ...,
    ) -> FileInput[AnyStr]: ...

elif sys.version_info >= (3, 8):
    def input(
        files: StrOrBytesPath | Iterable[StrOrBytesPath] | None = ...,
        inplace: bool = ...,
        backup: str = ...,
        *,
        mode: str = ...,
        openhook: Callable[[StrOrBytesPath, str], IO[AnyStr]] = ...,
    ) -> FileInput[AnyStr]: ...

else:
    def input(
        files: StrOrBytesPath | Iterable[StrOrBytesPath] | None = ...,
        inplace: bool = ...,
        backup: str = ...,
        bufsize: int = ...,
        mode: str = ...,
        openhook: Callable[[StrOrBytesPath, str], IO[AnyStr]] = ...,
    ) -> FileInput[AnyStr]: ...

def close() -> None: ...
def nextfile() -> None: ...
def filename() -> str: ...
def lineno() -> int: ...
def filelineno() -> int: ...
def fileno() -> int: ...
def isfirstline() -> bool: ...
def isstdin() -> bool: ...

class FileInput(Iterator[AnyStr], Generic[AnyStr]):
    if sys.version_info >= (3, 10):
        def __init__(
            self,
            files: None | StrOrBytesPath | Iterable[StrOrBytesPath] = ...,
            inplace: bool = ...,
            backup: str = ...,
            *,
            mode: str = ...,
            openhook: Callable[[StrOrBytesPath, str], IO[AnyStr]] = ...,
            encoding: str | None = ...,
            errors: str | None = ...,
        ) -> None: ...
    elif sys.version_info >= (3, 8):
        def __init__(
            self,
            files: None | StrOrBytesPath | Iterable[StrOrBytesPath] = ...,
            inplace: bool = ...,
            backup: str = ...,
            *,
            mode: str = ...,
            openhook: Callable[[StrOrBytesPath, str], IO[AnyStr]] = ...,
        ) -> None: ...
    else:
        def __init__(
            self,
            files: None | StrOrBytesPath | Iterable[StrOrBytesPath] = ...,
            inplace: bool = ...,
            backup: str = ...,
            bufsize: int = ...,
            mode: str = ...,
            openhook: Callable[[StrOrBytesPath, str], IO[AnyStr]] = ...,
        ) -> None: ...

    def __del__(self) -> None: ...
    def close(self) -> None: ...
    def __enter__(self: Self) -> Self: ...
    def __exit__(
        self, type: type[BaseException] | None, value: BaseException | None, traceback: TracebackType | None
    ) -> None: ...
    def __iter__(self: Self) -> Self: ...
    def __next__(self) -> AnyStr: ...
    if sys.version_info < (3, 11):
        def __getitem__(self, i: int) -> AnyStr: ...

    def nextfile(self) -> None: ...
    def readline(self) -> AnyStr: ...
    def filename(self) -> str: ...
    def lineno(self) -> int: ...
    def filelineno(self) -> int: ...
    def fileno(self) -> int: ...
    def isfirstline(self) -> bool: ...
    def isstdin(self) -> bool: ...
    if sys.version_info >= (3, 9):
        def __class_getitem__(cls, item: Any) -> GenericAlias: ...

if sys.version_info >= (3, 10):
    def hook_compressed(
        filename: StrOrBytesPath, mode: str, *, encoding: str | None = ..., errors: str | None = ...
    ) -> IO[Any]: ...

else:
    def hook_compressed(filename: StrOrBytesPath, mode: str) -> IO[Any]: ...

def hook_encoded(encoding: str, errors: str | None = ...) -> Callable[[StrOrBytesPath, str], IO[Any]]: ...
