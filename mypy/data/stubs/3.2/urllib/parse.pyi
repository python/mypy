# Stubs for urllib.parse
from typing import List, Dict, Tuple, AnyStr, Generic, overload, Sequence, Mapping

__all__ = (
    'urlparse',
    'urlunparse',
    'urljoin',
    'urldefrag',
    'urlsplit',
    'urlunsplit',
    'urlencode',
    'parse_qs',
    'parse_qsl',
    'quote',
    'quote_plus',
    'quote_from_bytes',
    'unquote',
    'unquote_plus',
    'unquote_to_bytes'
)


class _ResultMixinBase(Generic[AnyStr]):
    def geturl(self) -> AnyStr: ...

class _ResultMixinStr(_ResultMixinBase[str]):
    def encode(self, encoding: str = 'ascii', errors: str = 'strict') -> '_ResultMixinBytes': ...


class _ResultMixinBytes(_ResultMixinBase[str]):
    def decode(self, encoding: str = 'ascii', errors: str = 'strict') -> '_ResultMixinStr': ...


class _NetlocResultMixinBase(Generic[AnyStr]):
    username = ... # type: AnyStr
    password = ... # type: AnyStr
    hostname = ... # type: AnyStr
    port = ... # type: int

class _NetlocResultMixinStr(_NetlocResultMixinBase[str], _ResultMixinStr): ...


class _NetlocResultMixinBytes(_NetlocResultMixinBase[str], _ResultMixinBytes): ...

class _DefragResultBase(tuple, Generic[AnyStr]):
    url = ... # type: AnyStr
    fragment = ... # type: AnyStr

class _SplitResultBase(tuple, Generic[AnyStr]):
    scheme = ... # type: AnyStr
    netloc = ... # type: AnyStr
    path = ... # type: AnyStr
    query = ... # type: AnyStr
    fragment = ... # type: AnyStr

class _ParseResultBase(tuple, Generic[AnyStr]):
    scheme = ... # type: AnyStr
    netloc = ... # type: AnyStr
    path = ... # type: AnyStr
    params = ... # type: AnyStr
    query = ... # type: AnyStr
    fragment = ... # type: AnyStr

# Structured result objects for string data
class DefragResult(_DefragResultBase[str], _ResultMixinStr): ...

class SplitResult(_SplitResultBase[str], _NetlocResultMixinStr): ...

class ParseResult(_ParseResultBase[str], _NetlocResultMixinStr): ...

# Structured result objects for bytes data
class DefragResultBytes(_DefragResultBase[bytes], _ResultMixinBytes): ...

class SplitResultBytes(_SplitResultBase[bytes], _NetlocResultMixinBytes): ...

class ParseResultBytes(_ParseResultBase[bytes], _NetlocResultMixinBytes): ...


def parse_qs(qs: str, keep_blank_values : bool = False, strict_parsing : bool = False, encoding : str = 'utf-8', errors: str = 'replace') -> Dict[str, List[str]]: ...

def parse_qsl(qs: str, keep_blank_values: bool = False, strict_parsing: bool = False, encoding: str = 'utf-8', errors: str = 'replace') -> List[Tuple[str,str]]: ...

def quote(string: AnyStr, safe: AnyStr = None, encoding: str = None, errors: str = None) -> str: ...

def quote_from_bytes(bs: bytes, safe: AnyStr = None) -> bytes: ...

def quote_plus(string: AnyStr, safe: AnyStr = None, encoding: str = None, errors: str = None) -> str: ...

def unquote(string: str, encoding: str = 'utf-8', errors: str = 'replace') -> str: ...

def unquote_to_bytes(string: AnyStr) -> bytes: ...

@overload
def urldefrag(url: str) -> DefragResult: ...
@overload
def urldefrag(url: bytes) -> DefragResultBytes: ...

@overload
def urlencode(query: Mapping[AnyStr, AnyStr], doseq: bool = False, safe: AnyStr = None, encoding: str = None, errors: str = None) -> str: ...
@overload
def urlencode(query: Sequence[Tuple[AnyStr, AnyStr]], doseq: bool = False, safe: AnyStr = None, encoding: str = None, errors: str = None) -> str: ...

def urljoin(base: AnyStr, url: AnyStr, allow_fragments: bool = True) -> AnyStr: ...

@overload
def urlparse(url: str, scheme: str = None, allow_framgents: bool = True) -> ParseResult: ...
@overload
def urlparse(url: bytes, scheme: bytes = None, allow_framgents: bool = True) -> ParseResultBytes: ...

@overload
def urlsplit(url: str, scheme: str = None, allow_fragments: bool = True) -> SplitResult: ...
@overload
def urlsplit(url: bytes, scheme: bytes = None, allow_fragments: bool = True) -> SplitResultBytes: ...

@overload
def urlunparse(components: Sequence[AnyStr]) -> AnyStr: ...
@overload
def urlunparse(components: Tuple[AnyStr, AnyStr, AnyStr, AnyStr, AnyStr, AnyStr]) -> AnyStr: ...

@overload
def urlunsplit(components: Sequence[AnyStr]) -> AnyStr: ...
@overload
def urlunsplit(components: Tuple[AnyStr, AnyStr, AnyStr, AnyStr, AnyStr]) -> AnyStr: ...
