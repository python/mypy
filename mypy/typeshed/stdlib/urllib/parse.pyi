import sys
from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import Any, AnyStr, Generic, NamedTuple, TypeVar, overload

if sys.version_info >= (3, 9):
    from types import GenericAlias

__all__ = [
    "urlparse",
    "urlunparse",
    "urljoin",
    "urldefrag",
    "urlsplit",
    "urlunsplit",
    "urlencode",
    "parse_qs",
    "parse_qsl",
    "quote",
    "quote_plus",
    "quote_from_bytes",
    "unquote",
    "unquote_plus",
    "unquote_to_bytes",
    "DefragResult",
    "ParseResult",
    "SplitResult",
    "DefragResultBytes",
    "ParseResultBytes",
    "SplitResultBytes",
]

uses_relative: list[str]
uses_netloc: list[str]
uses_params: list[str]
non_hierarchical: list[str]
uses_query: list[str]
uses_fragment: list[str]
scheme_chars: str
if sys.version_info < (3, 11):
    MAX_CACHE_SIZE: int

class _ResultMixinBase(Generic[AnyStr]):
    def geturl(self) -> AnyStr: ...

class _ResultMixinStr(_ResultMixinBase[str]):
    def encode(self, encoding: str = ..., errors: str = ...) -> _ResultMixinBytes: ...

class _ResultMixinBytes(_ResultMixinBase[bytes]):
    def decode(self, encoding: str = ..., errors: str = ...) -> _ResultMixinStr: ...

class _NetlocResultMixinBase(Generic[AnyStr]):
    @property
    def username(self) -> AnyStr | None: ...
    @property
    def password(self) -> AnyStr | None: ...
    @property
    def hostname(self) -> AnyStr | None: ...
    @property
    def port(self) -> int | None: ...
    if sys.version_info >= (3, 9):
        def __class_getitem__(cls, item: Any) -> GenericAlias: ...

class _NetlocResultMixinStr(_NetlocResultMixinBase[str], _ResultMixinStr): ...
class _NetlocResultMixinBytes(_NetlocResultMixinBase[bytes], _ResultMixinBytes): ...

# Ideally this would be a generic fixed-length tuple,
# but mypy doesn't support that yet: https://github.com/python/mypy/issues/685#issuecomment-992014179
class _DefragResultBase(tuple[AnyStr, ...], Generic[AnyStr]):
    if sys.version_info >= (3, 10):
        __match_args__ = ("url", "fragment")
    @property
    def url(self) -> AnyStr: ...
    @property
    def fragment(self) -> AnyStr: ...

class _SplitResultBase(NamedTuple):
    scheme: str
    netloc: str
    path: str
    query: str
    fragment: str

class _SplitResultBytesBase(NamedTuple):
    scheme: bytes
    netloc: bytes
    path: bytes
    query: bytes
    fragment: bytes

class _ParseResultBase(NamedTuple):
    scheme: str
    netloc: str
    path: str
    params: str
    query: str
    fragment: str

class _ParseResultBytesBase(NamedTuple):
    scheme: bytes
    netloc: bytes
    path: bytes
    params: bytes
    query: bytes
    fragment: bytes

# Structured result objects for string data
class DefragResult(_DefragResultBase[str], _ResultMixinStr): ...
class SplitResult(_SplitResultBase, _NetlocResultMixinStr): ...
class ParseResult(_ParseResultBase, _NetlocResultMixinStr): ...

# Structured result objects for bytes data
class DefragResultBytes(_DefragResultBase[bytes], _ResultMixinBytes): ...
class SplitResultBytes(_SplitResultBytesBase, _NetlocResultMixinBytes): ...
class ParseResultBytes(_ParseResultBytesBase, _NetlocResultMixinBytes): ...

def parse_qs(
    qs: AnyStr | None,
    keep_blank_values: bool = ...,
    strict_parsing: bool = ...,
    encoding: str = ...,
    errors: str = ...,
    max_num_fields: int | None = ...,
    separator: str = ...,
) -> dict[AnyStr, list[AnyStr]]: ...
def parse_qsl(
    qs: AnyStr | None,
    keep_blank_values: bool = ...,
    strict_parsing: bool = ...,
    encoding: str = ...,
    errors: str = ...,
    max_num_fields: int | None = ...,
    separator: str = ...,
) -> list[tuple[AnyStr, AnyStr]]: ...
@overload
def quote(string: str, safe: str | Iterable[int] = ..., encoding: str | None = ..., errors: str | None = ...) -> str: ...
@overload
def quote(string: bytes | bytearray, safe: str | Iterable[int] = ...) -> str: ...
def quote_from_bytes(bs: bytes | bytearray, safe: str | Iterable[int] = ...) -> str: ...
@overload
def quote_plus(string: str, safe: str | Iterable[int] = ..., encoding: str | None = ..., errors: str | None = ...) -> str: ...
@overload
def quote_plus(string: bytes | bytearray, safe: str | Iterable[int] = ...) -> str: ...

if sys.version_info >= (3, 9):
    def unquote(string: str | bytes, encoding: str = ..., errors: str = ...) -> str: ...

else:
    def unquote(string: str, encoding: str = ..., errors: str = ...) -> str: ...

def unquote_to_bytes(string: str | bytes | bytearray) -> bytes: ...
def unquote_plus(string: str, encoding: str = ..., errors: str = ...) -> str: ...
@overload
def urldefrag(url: str) -> DefragResult: ...
@overload
def urldefrag(url: bytes | bytearray | None) -> DefragResultBytes: ...

_Q = TypeVar("_Q", bound=str | Iterable[int])

def urlencode(
    query: Mapping[Any, Any] | Mapping[Any, Sequence[Any]] | Sequence[tuple[Any, Any]] | Sequence[tuple[Any, Sequence[Any]]],
    doseq: bool = False,
    safe: _Q = ...,
    encoding: str | None = None,
    errors: str | None = None,
    quote_via: Callable[[AnyStr, _Q, str, str], str] = ...,
) -> str: ...
def urljoin(base: AnyStr, url: AnyStr | None, allow_fragments: bool = ...) -> AnyStr: ...
@overload
def urlparse(url: str, scheme: str | None = ..., allow_fragments: bool = ...) -> ParseResult: ...
@overload
def urlparse(
    url: bytes | bytearray | None, scheme: bytes | bytearray | None = ..., allow_fragments: bool = ...
) -> ParseResultBytes: ...
@overload
def urlsplit(url: str, scheme: str | None = ..., allow_fragments: bool = ...) -> SplitResult: ...

if sys.version_info >= (3, 11):
    @overload
    def urlsplit(url: bytes | None, scheme: bytes | None = ..., allow_fragments: bool = ...) -> SplitResultBytes: ...

else:
    @overload
    def urlsplit(
        url: bytes | bytearray | None, scheme: bytes | bytearray | None = ..., allow_fragments: bool = ...
    ) -> SplitResultBytes: ...

@overload
def urlunparse(
    components: tuple[AnyStr | None, AnyStr | None, AnyStr | None, AnyStr | None, AnyStr | None, AnyStr | None]
) -> AnyStr: ...
@overload
def urlunparse(components: Sequence[AnyStr | None]) -> AnyStr: ...
@overload
def urlunsplit(components: tuple[AnyStr | None, AnyStr | None, AnyStr | None, AnyStr | None, AnyStr | None]) -> AnyStr: ...
@overload
def urlunsplit(components: Sequence[AnyStr | None]) -> AnyStr: ...
def unwrap(url: str) -> str: ...
