from collections.abc import Iterable, Iterator
from typing import Any, Protocol, Union
from typing_extensions import Literal, TypeAlias

__version__: str

QUOTE_ALL: Literal[1]
QUOTE_MINIMAL: Literal[0]
QUOTE_NONE: Literal[3]
QUOTE_NONNUMERIC: Literal[2]

class Error(Exception): ...

class Dialect:
    delimiter: str
    quotechar: str | None
    escapechar: str | None
    doublequote: bool
    skipinitialspace: bool
    lineterminator: str
    quoting: int
    strict: int
    def __init__(self) -> None: ...

_DialectLike: TypeAlias = Union[str, Dialect, type[Dialect]]

class _reader(Iterator[list[str]]):
    dialect: Dialect
    line_num: int
    def __next__(self) -> list[str]: ...

class _writer:
    dialect: Dialect
    def writerow(self, row: Iterable[Any]) -> Any: ...
    def writerows(self, rows: Iterable[Iterable[Any]]) -> None: ...

class _Writer(Protocol):
    def write(self, __s: str) -> object: ...

def writer(csvfile: _Writer, dialect: _DialectLike = ..., **fmtparams: Any) -> _writer: ...
def reader(csvfile: Iterable[str], dialect: _DialectLike = ..., **fmtparams: Any) -> _reader: ...
def register_dialect(name: str, dialect: Any = ..., **fmtparams: Any) -> None: ...
def unregister_dialect(name: str) -> None: ...
def get_dialect(name: str) -> Dialect: ...
def list_dialects() -> list[str]: ...
def field_size_limit(new_limit: int = ...) -> int: ...
