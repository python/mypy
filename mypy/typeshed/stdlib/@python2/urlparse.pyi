from typing import AnyStr, NamedTuple, Sequence, overload

_String = str | unicode

uses_relative: list[str]
uses_netloc: list[str]
uses_params: list[str]
non_hierarchical: list[str]
uses_query: list[str]
uses_fragment: list[str]
scheme_chars: str
MAX_CACHE_SIZE: int

def clear_cache() -> None: ...

class ResultMixin(object):
    @property
    def username(self) -> str | None: ...
    @property
    def password(self) -> str | None: ...
    @property
    def hostname(self) -> str | None: ...
    @property
    def port(self) -> int | None: ...

class _SplitResult(NamedTuple):
    scheme: str
    netloc: str
    path: str
    query: str
    fragment: str

class SplitResult(_SplitResult, ResultMixin):
    def geturl(self) -> str: ...

class _ParseResult(NamedTuple):
    scheme: str
    netloc: str
    path: str
    params: str
    query: str
    fragment: str

class ParseResult(_ParseResult, ResultMixin):
    def geturl(self) -> _String: ...

def urlparse(url: _String, scheme: _String = ..., allow_fragments: bool = ...) -> ParseResult: ...
def urlsplit(url: _String, scheme: _String = ..., allow_fragments: bool = ...) -> SplitResult: ...
@overload
def urlunparse(data: tuple[AnyStr, AnyStr, AnyStr, AnyStr, AnyStr, AnyStr]) -> AnyStr: ...
@overload
def urlunparse(data: Sequence[AnyStr]) -> AnyStr: ...
@overload
def urlunsplit(data: tuple[AnyStr, AnyStr, AnyStr, AnyStr, AnyStr]) -> AnyStr: ...
@overload
def urlunsplit(data: Sequence[AnyStr]) -> AnyStr: ...
def urljoin(base: AnyStr, url: AnyStr, allow_fragments: bool = ...) -> AnyStr: ...
def urldefrag(url: AnyStr) -> tuple[AnyStr, AnyStr]: ...
def unquote(s: AnyStr) -> AnyStr: ...
def parse_qs(qs: AnyStr, keep_blank_values: bool = ..., strict_parsing: bool = ...) -> dict[AnyStr, list[AnyStr]]: ...
def parse_qsl(qs: AnyStr, keep_blank_values: int = ..., strict_parsing: bool = ...) -> list[tuple[AnyStr, AnyStr]]: ...
