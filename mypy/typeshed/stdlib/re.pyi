import enum
import sre_compile
import sys
from sre_constants import error as error
from typing import Any, AnyStr, Callable, Iterator, overload

# ----- re variables and constants -----
if sys.version_info >= (3, 7):
    from typing import Match as Match, Pattern as Pattern
else:
    from typing import Match, Pattern

if sys.version_info >= (3, 11):
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
        "Pattern",
        "Match",
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
        "RegexFlag",
        "NOFLAG",
    ]
elif sys.version_info >= (3, 8):
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
        "Pattern",
        "Match",
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
else:
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
_FlagsType = int | RegexFlag

if sys.version_info < (3, 7):
    # undocumented
    _pattern_type: type

# Type-wise these overloads are unnecessary, they could also be modeled using
# unions in the parameter types. However mypy has a bug regarding TypeVar
# constraints (https://github.com/python/mypy/issues/11880),
# which limits us here because AnyStr is a constrained TypeVar.

@overload
def compile(pattern: AnyStr, flags: _FlagsType = ...) -> Pattern[AnyStr]: ...
@overload
def compile(pattern: Pattern[AnyStr], flags: _FlagsType = ...) -> Pattern[AnyStr]: ...
@overload
def search(pattern: AnyStr, string: AnyStr, flags: _FlagsType = ...) -> Match[AnyStr] | None: ...
@overload
def search(pattern: Pattern[AnyStr], string: AnyStr, flags: _FlagsType = ...) -> Match[AnyStr] | None: ...
@overload
def match(pattern: AnyStr, string: AnyStr, flags: _FlagsType = ...) -> Match[AnyStr] | None: ...
@overload
def match(pattern: Pattern[AnyStr], string: AnyStr, flags: _FlagsType = ...) -> Match[AnyStr] | None: ...
@overload
def fullmatch(pattern: AnyStr, string: AnyStr, flags: _FlagsType = ...) -> Match[AnyStr] | None: ...
@overload
def fullmatch(pattern: Pattern[AnyStr], string: AnyStr, flags: _FlagsType = ...) -> Match[AnyStr] | None: ...
@overload
def split(pattern: AnyStr, string: AnyStr, maxsplit: int = ..., flags: _FlagsType = ...) -> list[AnyStr | Any]: ...
@overload
def split(pattern: Pattern[AnyStr], string: AnyStr, maxsplit: int = ..., flags: _FlagsType = ...) -> list[AnyStr | Any]: ...
@overload
def findall(pattern: AnyStr, string: AnyStr, flags: _FlagsType = ...) -> list[Any]: ...
@overload
def findall(pattern: Pattern[AnyStr], string: AnyStr, flags: _FlagsType = ...) -> list[Any]: ...

# Return an iterator yielding match objects over all non-overlapping matches
# for the RE pattern in string. The string is scanned left-to-right, and
# matches are returned in the order found. Empty matches are included in the
# result unless they touch the beginning of another match.
@overload
def finditer(pattern: AnyStr, string: AnyStr, flags: _FlagsType = ...) -> Iterator[Match[AnyStr]]: ...
@overload
def finditer(pattern: Pattern[AnyStr], string: AnyStr, flags: _FlagsType = ...) -> Iterator[Match[AnyStr]]: ...
@overload
def sub(pattern: AnyStr, repl: AnyStr, string: AnyStr, count: int = ..., flags: _FlagsType = ...) -> AnyStr: ...
@overload
def sub(
    pattern: AnyStr, repl: Callable[[Match[AnyStr]], AnyStr], string: AnyStr, count: int = ..., flags: _FlagsType = ...
) -> AnyStr: ...
@overload
def sub(pattern: Pattern[AnyStr], repl: AnyStr, string: AnyStr, count: int = ..., flags: _FlagsType = ...) -> AnyStr: ...
@overload
def sub(
    pattern: Pattern[AnyStr], repl: Callable[[Match[AnyStr]], AnyStr], string: AnyStr, count: int = ..., flags: _FlagsType = ...
) -> AnyStr: ...
@overload
def subn(pattern: AnyStr, repl: AnyStr, string: AnyStr, count: int = ..., flags: _FlagsType = ...) -> tuple[AnyStr, int]: ...
@overload
def subn(
    pattern: AnyStr, repl: Callable[[Match[AnyStr]], AnyStr], string: AnyStr, count: int = ..., flags: _FlagsType = ...
) -> tuple[AnyStr, int]: ...
@overload
def subn(
    pattern: Pattern[AnyStr], repl: AnyStr, string: AnyStr, count: int = ..., flags: _FlagsType = ...
) -> tuple[AnyStr, int]: ...
@overload
def subn(
    pattern: Pattern[AnyStr], repl: Callable[[Match[AnyStr]], AnyStr], string: AnyStr, count: int = ..., flags: _FlagsType = ...
) -> tuple[AnyStr, int]: ...
def escape(pattern: AnyStr) -> AnyStr: ...
def purge() -> None: ...
def template(pattern: AnyStr | Pattern[AnyStr], flags: _FlagsType = ...) -> Pattern[AnyStr]: ...
