import sys
from _typeshed import Self, SupportsGetItem, SupportsItemAccess
from builtins import list as _list, type as _type
from collections.abc import Iterable, Iterator, Mapping
from types import TracebackType
from typing import IO, Any, Protocol

if sys.version_info >= (3, 8):
    __all__ = [
        "MiniFieldStorage",
        "FieldStorage",
        "parse",
        "parse_multipart",
        "parse_header",
        "test",
        "print_exception",
        "print_environ",
        "print_form",
        "print_directory",
        "print_arguments",
        "print_environ_usage",
    ]
else:
    __all__ = [
        "MiniFieldStorage",
        "FieldStorage",
        "parse",
        "parse_qs",
        "parse_qsl",
        "parse_multipart",
        "parse_header",
        "test",
        "print_exception",
        "print_environ",
        "print_form",
        "print_directory",
        "print_arguments",
        "print_environ_usage",
        "escape",
    ]

def parse(
    fp: IO[Any] | None = ...,
    environ: SupportsItemAccess[str, str] = ...,
    keep_blank_values: bool = ...,
    strict_parsing: bool = ...,
    separator: str = ...,
) -> dict[str, list[str]]: ...

if sys.version_info < (3, 8):
    def parse_qs(qs: str, keep_blank_values: bool = ..., strict_parsing: bool = ...) -> dict[str, list[str]]: ...
    def parse_qsl(qs: str, keep_blank_values: bool = ..., strict_parsing: bool = ...) -> list[tuple[str, str]]: ...

if sys.version_info >= (3, 7):
    def parse_multipart(
        fp: IO[Any], pdict: SupportsGetItem[str, bytes], encoding: str = ..., errors: str = ..., separator: str = ...
    ) -> dict[str, list[Any]]: ...

else:
    def parse_multipart(fp: IO[Any], pdict: SupportsGetItem[str, bytes]) -> dict[str, list[bytes]]: ...

class _Environ(Protocol):
    def __getitem__(self, __k: str) -> str: ...
    def keys(self) -> Iterable[str]: ...

def parse_header(line: str) -> tuple[str, dict[str, str]]: ...
def test(environ: _Environ = ...) -> None: ...
def print_environ(environ: _Environ = ...) -> None: ...
def print_form(form: dict[str, Any]) -> None: ...
def print_directory() -> None: ...
def print_environ_usage() -> None: ...

if sys.version_info < (3, 8):
    def escape(s: str, quote: bool | None = ...) -> str: ...

class MiniFieldStorage:
    # The first five "Any" attributes here are always None, but mypy doesn't support that
    filename: Any
    list: Any
    type: Any
    file: IO[bytes] | None
    type_options: dict[Any, Any]
    disposition: Any
    disposition_options: dict[Any, Any]
    headers: dict[Any, Any]
    name: Any
    value: Any
    def __init__(self, name: Any, value: Any) -> None: ...

class FieldStorage:
    FieldStorageClass: _type | None
    keep_blank_values: int
    strict_parsing: int
    qs_on_post: str | None
    headers: Mapping[str, str]
    fp: IO[bytes]
    encoding: str
    errors: str
    outerboundary: bytes
    bytes_read: int
    limit: int | None
    disposition: str
    disposition_options: dict[str, str]
    filename: str | None
    file: IO[bytes] | None
    type: str
    type_options: dict[str, str]
    innerboundary: bytes
    length: int
    done: int
    list: _list[Any] | None
    value: None | bytes | _list[Any]
    def __init__(
        self,
        fp: IO[Any] | None = ...,
        headers: Mapping[str, str] | None = ...,
        outerboundary: bytes = ...,
        environ: SupportsGetItem[str, str] = ...,
        keep_blank_values: int = ...,
        strict_parsing: int = ...,
        limit: int | None = ...,
        encoding: str = ...,
        errors: str = ...,
        max_num_fields: int | None = ...,
        separator: str = ...,
    ) -> None: ...
    def __enter__(self: Self) -> Self: ...
    def __exit__(self, *args: object) -> None: ...
    def __iter__(self) -> Iterator[str]: ...
    def __getitem__(self, key: str) -> Any: ...
    def getvalue(self, key: str, default: Any = ...) -> Any: ...
    def getfirst(self, key: str, default: Any = ...) -> Any: ...
    def getlist(self, key: str) -> _list[Any]: ...
    def keys(self) -> _list[str]: ...
    def __contains__(self, key: str) -> bool: ...
    def __len__(self) -> int: ...
    def __bool__(self) -> bool: ...
    # In Python 3 it returns bytes or str IO depending on an internal flag
    def make_file(self) -> IO[Any]: ...

def print_exception(
    type: type[BaseException] | None = ...,
    value: BaseException | None = ...,
    tb: TracebackType | None = ...,
    limit: int | None = ...,
) -> None: ...
def print_arguments() -> None: ...
