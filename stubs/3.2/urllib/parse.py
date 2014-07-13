# Stubs for urllib.parse
from typing import List, Dict, Tuple, AnyStr, Undefined, Generic, overload, Sequence, Mapping

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
    def geturl(self) -> AnyStr: pass

class _ResultMixinStr(_ResultMixinBase[str]):
    def encode(self, encoding: str = 'ascii', errors: str = 'strict') -> '_ResultMixinBytes': pass


class _ResultMixinBytes(_ResultMixinBase[str]):
    def decode(self, encoding: str = 'ascii', errors: str = 'strict') -> '_ResultMixinStr': pass


class _NetlocResultMixinBase(Generic[AnyStr]):
    username = Undefined(AnyStr)
    password = Undefined(AnyStr)
    hostname = Undefined(AnyStr)
    port = Undefined(int)

class _NetlocResultMixinStr(_NetlocResultMixinBase[str], _ResultMixinStr): pass


class _NetlocResultMixinBytes(_NetlocResultMixinBase[str], _ResultMixinBytes): pass

class _DefragResultBase(tuple, Generic[AnyStr]):
    url = Undefined(AnyStr)
    fragment = Undefined(AnyStr)

class _SplitResultBase(tuple, Generic[AnyStr]):
    scheme = Undefined(AnyStr)
    netloc = Undefined(AnyStr)
    path = Undefined(AnyStr)
    query = Undefined(AnyStr)
    fragment = Undefined(AnyStr)

class _ParseResultBase(tuple, Generic[AnyStr]):
    scheme = Undefined(AnyStr)
    netloc = Undefined(AnyStr)
    path = Undefined(AnyStr)
    params = Undefined(AnyStr)
    query = Undefined(AnyStr)
    fragment = Undefined(AnyStr)

# Structured result objects for string data
class DefragResult(_DefragResultBase[str], _ResultMixinStr): pass

class SplitResult(_SplitResultBase[str], _NetlocResultMixinStr): pass

class ParseResult(_ParseResultBase[str], _NetlocResultMixinStr): pass

# Structured result objects for bytes data
class DefragResultBytes(_DefragResultBase[bytes], _ResultMixinBytes): pass

class SplitResultBytes(_SplitResultBase[bytes], _NetlocResultMixinBytes): pass

class ParseResultBytes(_ParseResultBase[bytes], _NetlocResultMixinBytes): pass


def parse_qs(qs: str, keep_blank_values : bool = False, strict_parsing : bool = False, encoding : str = 'utf-8', errors: str = 'replace') -> Dict[str, List[str]]: pass

def parse_qsl(qs: str, keep_blank_values: bool = False, strict_parsing: bool = False, encoding: str = 'utf-8', errors: str = 'replace') -> List[Tuple[str,str]]: pass

def quote(string: AnyStr, safe: AnyStr = None, encoding: str = None, errors: str = None) -> str: pass

def quote_from_bytes(bs: bytes, safe: AnyStr = None) -> bytes: pass

def quote_plus(string: AnyStr, safe: AnyStr = None, encoding: str = None, errors: str = None) -> str: pass

def unquote(string: str, encoding: str = 'utf-8', errors: str = 'replace') -> str: pass

def unquote_to_bytes(string: AnyStr) -> bytes: pass

@overload
def urldefrag(url: str) -> DefragResult: pass
@overload
def urldefrag(url: bytes) -> DefragResultBytes: pass

@overload
def urlencode(query: Mapping[AnyStr, AnyStr], doseq: bool = False, safe: AnyStr = None, encoding: str = None, errors: str = None) -> str: pass
@overload
def urlencode(query: Sequence[Tuple[AnyStr, AnyStr]], doseq: bool = False, safe: AnyStr = None, encoding: str = None, errors: str = None) -> str: pass

def urljoin(base: AnyStr, url: AnyStr, allow_fragments: bool = True) -> AnyStr: pass

@overload
def urlparse(url: str, scheme: str = None, allow_framgents: bool = True) -> ParseResult: pass
@overload
def urlparse(url: bytes, scheme: bytes = None, allow_framgents: bool = True) -> ParseResultBytes: pass

@overload
def urlsplit(url: str, scheme: str = None, allow_fragments: bool = True) -> SplitResult: pass
@overload
def urlsplit(url: bytes, scheme: bytes = None, allow_fragments: bool = True) -> SplitResultBytes: pass

@overload
def urlunparse(components: Sequence[AnyStr]) -> AnyStr: pass
@overload
def urlunparse(components: Tuple[AnyStr, AnyStr, AnyStr, AnyStr, AnyStr, AnyStr]) -> AnyStr: pass

@overload
def urlunsplit(components: Sequence[AnyStr]) -> AnyStr: pass
@overload
def urlunsplit(components: Tuple[AnyStr, AnyStr, AnyStr, AnyStr, AnyStr]) -> AnyStr: pass
