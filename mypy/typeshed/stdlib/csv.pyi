import sys
from _csv import (
    QUOTE_ALL as QUOTE_ALL,
    QUOTE_MINIMAL as QUOTE_MINIMAL,
    QUOTE_NONE as QUOTE_NONE,
    QUOTE_NONNUMERIC as QUOTE_NONNUMERIC,
    Dialect as Dialect,
    Error as Error,
    __version__ as __version__,
    _DialectLike,
    _reader,
    _writer,
    field_size_limit as field_size_limit,
    get_dialect as get_dialect,
    list_dialects as list_dialects,
    reader as reader,
    register_dialect as register_dialect,
    unregister_dialect as unregister_dialect,
    writer as writer,
)
from _typeshed import Self
from collections.abc import Collection, Iterable, Iterator, Mapping, Sequence
from typing import Any, Generic, TypeVar, overload

if sys.version_info >= (3, 8):
    from builtins import dict as _DictReadMapping
else:
    from collections import OrderedDict as _DictReadMapping

__all__ = [
    "QUOTE_MINIMAL",
    "QUOTE_ALL",
    "QUOTE_NONNUMERIC",
    "QUOTE_NONE",
    "Error",
    "Dialect",
    "__doc__",
    "excel",
    "excel_tab",
    "field_size_limit",
    "reader",
    "writer",
    "register_dialect",
    "get_dialect",
    "list_dialects",
    "Sniffer",
    "unregister_dialect",
    "__version__",
    "DictReader",
    "DictWriter",
    "unix_dialect",
]

_T = TypeVar("_T")

class excel(Dialect):
    delimiter: str
    quotechar: str
    doublequote: bool
    skipinitialspace: bool
    lineterminator: str
    quoting: int

class excel_tab(excel):
    delimiter: str

class unix_dialect(Dialect):
    delimiter: str
    quotechar: str
    doublequote: bool
    skipinitialspace: bool
    lineterminator: str
    quoting: int

class DictReader(Generic[_T], Iterator[_DictReadMapping[_T, str]]):
    fieldnames: Sequence[_T] | None
    restkey: str | None
    restval: str | None
    reader: _reader
    dialect: _DialectLike
    line_num: int
    @overload
    def __init__(
        self,
        f: Iterable[str],
        fieldnames: Sequence[_T],
        restkey: str | None = ...,
        restval: str | None = ...,
        dialect: _DialectLike = ...,
        *args: Any,
        **kwds: Any,
    ) -> None: ...
    @overload
    def __init__(
        self: DictReader[str],
        f: Iterable[str],
        fieldnames: Sequence[str] | None = ...,
        restkey: str | None = ...,
        restval: str | None = ...,
        dialect: _DialectLike = ...,
        *args: Any,
        **kwds: Any,
    ) -> None: ...
    def __iter__(self: Self) -> Self: ...
    def __next__(self) -> _DictReadMapping[_T, str]: ...

class DictWriter(Generic[_T]):
    fieldnames: Collection[_T]
    restval: Any | None
    extrasaction: str
    writer: _writer
    def __init__(
        self,
        f: Any,
        fieldnames: Collection[_T],
        restval: Any | None = ...,
        extrasaction: str = ...,
        dialect: _DialectLike = ...,
        *args: Any,
        **kwds: Any,
    ) -> None: ...
    if sys.version_info >= (3, 8):
        def writeheader(self) -> Any: ...
    else:
        def writeheader(self) -> None: ...

    def writerow(self, rowdict: Mapping[_T, Any]) -> Any: ...
    def writerows(self, rowdicts: Iterable[Mapping[_T, Any]]) -> None: ...

class Sniffer:
    preferred: list[str]
    def __init__(self) -> None: ...
    def sniff(self, sample: str, delimiters: str | None = ...) -> type[Dialect]: ...
    def has_header(self, sample: str) -> bool: ...
