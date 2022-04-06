import sys
from _typeshed import Self, SupportsWrite
from types import FrameType, TracebackType
from typing import IO, Any, Generator, Iterable, Iterator, Mapping, overload
from typing_extensions import Literal

__all__ = [
    "extract_stack",
    "extract_tb",
    "format_exception",
    "format_exception_only",
    "format_list",
    "format_stack",
    "format_tb",
    "print_exc",
    "format_exc",
    "print_exception",
    "print_last",
    "print_stack",
    "print_tb",
    "clear_frames",
    "FrameSummary",
    "StackSummary",
    "TracebackException",
    "walk_stack",
    "walk_tb",
]

_PT = tuple[str, int, str, str | None]

def print_tb(tb: TracebackType | None, limit: int | None = ..., file: IO[str] | None = ...) -> None: ...

if sys.version_info >= (3, 10):
    @overload
    def print_exception(
        __exc: type[BaseException] | None,
        value: BaseException | None = ...,
        tb: TracebackType | None = ...,
        limit: int | None = ...,
        file: IO[str] | None = ...,
        chain: bool = ...,
    ) -> None: ...
    @overload
    def print_exception(
        __exc: BaseException, *, limit: int | None = ..., file: IO[str] | None = ..., chain: bool = ...
    ) -> None: ...
    @overload
    def format_exception(
        __exc: type[BaseException] | None,
        value: BaseException | None = ...,
        tb: TracebackType | None = ...,
        limit: int | None = ...,
        chain: bool = ...,
    ) -> list[str]: ...
    @overload
    def format_exception(__exc: BaseException, *, limit: int | None = ..., chain: bool = ...) -> list[str]: ...

else:
    def print_exception(
        etype: type[BaseException] | None,
        value: BaseException | None,
        tb: TracebackType | None,
        limit: int | None = ...,
        file: IO[str] | None = ...,
        chain: bool = ...,
    ) -> None: ...
    def format_exception(
        etype: type[BaseException] | None,
        value: BaseException | None,
        tb: TracebackType | None,
        limit: int | None = ...,
        chain: bool = ...,
    ) -> list[str]: ...

def print_exc(limit: int | None = ..., file: IO[str] | None = ..., chain: bool = ...) -> None: ...
def print_last(limit: int | None = ..., file: IO[str] | None = ..., chain: bool = ...) -> None: ...
def print_stack(f: FrameType | None = ..., limit: int | None = ..., file: IO[str] | None = ...) -> None: ...
def extract_tb(tb: TracebackType | None, limit: int | None = ...) -> StackSummary: ...
def extract_stack(f: FrameType | None = ..., limit: int | None = ...) -> StackSummary: ...
def format_list(extracted_list: list[FrameSummary]) -> list[str]: ...

# undocumented
def print_list(extracted_list: list[FrameSummary], file: SupportsWrite[str] | None = ...) -> None: ...

if sys.version_info >= (3, 10):
    def format_exception_only(__exc: type[BaseException] | None, value: BaseException | None = ...) -> list[str]: ...

else:
    def format_exception_only(etype: type[BaseException] | None, value: BaseException | None) -> list[str]: ...

def format_exc(limit: int | None = ..., chain: bool = ...) -> str: ...
def format_tb(tb: TracebackType | None, limit: int | None = ...) -> list[str]: ...
def format_stack(f: FrameType | None = ..., limit: int | None = ...) -> list[str]: ...
def clear_frames(tb: TracebackType) -> None: ...
def walk_stack(f: FrameType | None) -> Iterator[tuple[FrameType, int]]: ...
def walk_tb(tb: TracebackType | None) -> Iterator[tuple[FrameType, int]]: ...

class TracebackException:
    __cause__: TracebackException
    __context__: TracebackException
    __suppress_context__: bool
    stack: StackSummary
    exc_type: type[BaseException]
    filename: str
    lineno: int
    text: str
    offset: int
    msg: str
    if sys.version_info >= (3, 10):
        def __init__(
            self,
            exc_type: type[BaseException],
            exc_value: BaseException,
            exc_traceback: TracebackType | None,
            *,
            limit: int | None = ...,
            lookup_lines: bool = ...,
            capture_locals: bool = ...,
            compact: bool = ...,
            _seen: set[int] | None = ...,
        ) -> None: ...
        @classmethod
        def from_exception(
            cls: type[Self],
            exc: BaseException,
            *,
            limit: int | None = ...,
            lookup_lines: bool = ...,
            capture_locals: bool = ...,
            compact: bool = ...,
        ) -> Self: ...
    else:
        def __init__(
            self,
            exc_type: type[BaseException],
            exc_value: BaseException,
            exc_traceback: TracebackType | None,
            *,
            limit: int | None = ...,
            lookup_lines: bool = ...,
            capture_locals: bool = ...,
            _seen: set[int] | None = ...,
        ) -> None: ...
        @classmethod
        def from_exception(
            cls: type[Self], exc: BaseException, *, limit: int | None = ..., lookup_lines: bool = ..., capture_locals: bool = ...
        ) -> Self: ...

    def __eq__(self, other: object) -> bool: ...
    def format(self, *, chain: bool = ...) -> Generator[str, None, None]: ...
    def format_exception_only(self) -> Generator[str, None, None]: ...

class FrameSummary(Iterable[Any]):
    if sys.version_info >= (3, 11):
        def __init__(
            self,
            filename: str,
            lineno: int | None,
            name: str,
            *,
            lookup_line: bool = ...,
            locals: Mapping[str, str] | None = ...,
            line: str | None = ...,
            end_lineno: int | None = ...,
            colno: int | None = ...,
            end_colno: int | None = ...,
        ) -> None: ...
        end_lineno: int | None
        colno: int | None
        end_colno: int | None
    else:
        def __init__(
            self,
            filename: str,
            lineno: int | None,
            name: str,
            *,
            lookup_line: bool = ...,
            locals: Mapping[str, str] | None = ...,
            line: str | None = ...,
        ) -> None: ...
    filename: str
    lineno: int | None
    name: str
    locals: dict[str, str] | None
    @property
    def line(self) -> str | None: ...
    @overload
    def __getitem__(self, pos: Literal[0]) -> str: ...
    @overload
    def __getitem__(self, pos: Literal[1]) -> int: ...
    @overload
    def __getitem__(self, pos: Literal[2]) -> str: ...
    @overload
    def __getitem__(self, pos: Literal[3]) -> str | None: ...
    @overload
    def __getitem__(self, pos: int) -> Any: ...
    def __iter__(self) -> Iterator[Any]: ...
    def __eq__(self, other: object) -> bool: ...
    if sys.version_info >= (3, 8):
        def __len__(self) -> Literal[4]: ...

class StackSummary(list[FrameSummary]):
    @classmethod
    def extract(
        cls,
        frame_gen: Iterable[tuple[FrameType, int]],
        *,
        limit: int | None = ...,
        lookup_lines: bool = ...,
        capture_locals: bool = ...,
    ) -> StackSummary: ...
    @classmethod
    def from_list(cls, a_list: list[_PT]) -> StackSummary: ...
    def format(self) -> list[str]: ...
