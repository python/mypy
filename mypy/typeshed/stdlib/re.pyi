import enum
import sre_compile
import sys
from _typeshed import ReadableBuffer
from collections.abc import Callable, Iterator
from sre_constants import error as error
from typing import Any, AnyStr, overload
from typing_extensions import TypeAlias

# ----- re variables and constants -----
if sys.version_info >= (3, 7):
    from typing import Match as Match, Pattern as Pattern
else:
    from typing import Match, Pattern

__all__ = [
    "match",
    "fullmatch",
    "search",
    "sub",
    "subn",
    "split",
    "findall",
    "finditer",
    "compile",
    "purge",
    "template",
    "escape",
    "error",
    "A",
    "I",
    "L",
    "M",
    "S",
    "X",
    "U",
    "ASCII",
    "IGNORECASE",
    "LOCALE",
    "MULTILINE",
    "DOTALL",
    "VERBOSE",
    "UNICODE",
]

if sys.version_info >= (3, 7):
    __all__ += ["Match", "Pattern"]

if sys.version_info >= (3, 11):
    __all__ += ["NOFLAG", "RegexFlag"]

class RegexFlag(enum.IntFlag):
    A = sre_compile.SRE_FLAG_ASCII
    ASCII = A
    DEBUG = sre_compile.SRE_FLAG_DEBUG
    I = sre_compile.SRE_FLAG_IGNORECASE
    IGNORECASE = I
    L = sre_compile.SRE_FLAG_LOCALE
    LOCALE = L
    M = sre_compile.SRE_FLAG_MULTILINE
    MULTILINE = M
    S = sre_compile.SRE_FLAG_DOTALL
    DOTALL = S
    X = sre_compile.SRE_FLAG_VERBOSE
    VERBOSE = X
    U = sre_compile.SRE_FLAG_UNICODE
    UNICODE = U
    T = sre_compile.SRE_FLAG_TEMPLATE
    TEMPLATE = T
    if sys.version_info >= (3, 11):
        NOFLAG: int

A = RegexFlag.A
ASCII = RegexFlag.ASCII
DEBUG = RegexFlag.DEBUG
I = RegexFlag.I
IGNORECASE = RegexFlag.IGNORECASE
L = RegexFlag.L
LOCALE = RegexFlag.LOCALE
M = RegexFlag.M
MULTILINE = RegexFlag.MULTILINE
S = RegexFlag.S
DOTALL = RegexFlag.DOTALL
X = RegexFlag.X
VERBOSE = RegexFlag.VERBOSE
U = RegexFlag.U
UNICODE = RegexFlag.UNICODE
T = RegexFlag.T
TEMPLATE = RegexFlag.TEMPLATE
if sys.version_info >= (3, 11):
    NOFLAG = RegexFlag.NOFLAG
_FlagsType: TypeAlias = int | RegexFlag

if sys.version_info < (3, 7):
    # undocumented
    _pattern_type: type

# Type-wise the compile() overloads are unnecessary, they could also be modeled using
# unions in the parameter types. However mypy has a bug regarding TypeVar
# constraints (https://github.com/python/mypy/issues/11880),
# which limits us here because AnyStr is a constrained TypeVar.

# pattern arguments do *not* accept arbitrary buffers such as bytearray,
# because the pattern must be hashable.
@overload
def compile(pattern: AnyStr, flags: _FlagsType = ...) -> Pattern[AnyStr]: ...
@overload
def compile(pattern: Pattern[AnyStr], flags: _FlagsType = ...) -> Pattern[AnyStr]: ...
@overload
def search(pattern: str | Pattern[str], string: str, flags: _FlagsType = ...) -> Match[str] | None: ...
@overload
def search(pattern: bytes | Pattern[bytes], string: ReadableBuffer, flags: _FlagsType = ...) -> Match[bytes] | None: ...
@overload
def match(pattern: str | Pattern[str], string: str, flags: _FlagsType = ...) -> Match[str] | None: ...
@overload
def match(pattern: bytes | Pattern[bytes], string: ReadableBuffer, flags: _FlagsType = ...) -> Match[bytes] | None: ...
@overload
def fullmatch(pattern: str | Pattern[str], string: str, flags: _FlagsType = ...) -> Match[str] | None: ...
@overload
def fullmatch(pattern: bytes | Pattern[bytes], string: ReadableBuffer, flags: _FlagsType = ...) -> Match[bytes] | None: ...
@overload
def split(pattern: str | Pattern[str], string: str, maxsplit: int = ..., flags: _FlagsType = ...) -> list[str | Any]: ...
@overload
def split(
    pattern: bytes | Pattern[bytes], string: ReadableBuffer, maxsplit: int = ..., flags: _FlagsType = ...
) -> list[bytes | Any]: ...
@overload
def findall(pattern: str | Pattern[str], string: str, flags: _FlagsType = ...) -> list[Any]: ...
@overload
def findall(pattern: bytes | Pattern[bytes], string: ReadableBuffer, flags: _FlagsType = ...) -> list[Any]: ...
@overload
def finditer(pattern: str | Pattern[str], string: str, flags: _FlagsType = ...) -> Iterator[Match[str]]: ...
@overload
def finditer(pattern: bytes | Pattern[bytes], string: ReadableBuffer, flags: _FlagsType = ...) -> Iterator[Match[bytes]]: ...
@overload
def sub(
    pattern: str | Pattern[str], repl: str | Callable[[Match[str]], str], string: str, count: int = ..., flags: _FlagsType = ...
) -> str: ...
@overload
def sub(
    pattern: bytes | Pattern[bytes],
    repl: ReadableBuffer | Callable[[Match[bytes]], ReadableBuffer],
    string: ReadableBuffer,
    count: int = ...,
    flags: _FlagsType = ...,
) -> bytes: ...
@overload
def subn(
    pattern: str | Pattern[str], repl: str | Callable[[Match[str]], str], string: str, count: int = ..., flags: _FlagsType = ...
) -> tuple[str, int]: ...
@overload
def subn(
    pattern: bytes | Pattern[bytes],
    repl: ReadableBuffer | Callable[[Match[bytes]], ReadableBuffer],
    string: ReadableBuffer,
    count: int = ...,
    flags: _FlagsType = ...,
) -> tuple[bytes, int]: ...
def escape(pattern: AnyStr) -> AnyStr: ...
def purge() -> None: ...
def template(pattern: AnyStr | Pattern[AnyStr], flags: _FlagsType = ...) -> Pattern[AnyStr]: ...
