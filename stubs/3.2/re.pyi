# Stubs for re
# Ron Murawski <ron@horizonchess.com>
# 'bytes' support added by Jukka Lehtosalo

# based on: http://docs.python.org/3.2/library/re.html
# and http://hg.python.org/cpython/file/618ea5612e83/Lib/re.py

from typing import (
    Undefined, List, Iterator, overload, Function, Tuple, Sequence, Dict,
    Generic, AnyStr, Match, Pattern
)

# ----- re variables and constants -----
A = 0
ASCII = 0
DEBUG = 0
I = 0
IGNORECASE = 0
L = 0
LOCALE = 0
M = 0
MULTILINE = 0
S = 0
DOTALL = 0
X = 0
VERBOSE = 0
U = 0
UNICODE = 0

class error(Exception): pass

def compile(pattern: AnyStr, flags: int = 0) -> Pattern[AnyStr]: pass
def search(pattern: AnyStr, string: AnyStr,
           flags: int = 0) -> Match[AnyStr]: pass
def match(pattern: AnyStr, string: AnyStr,
          flags: int = 0) -> Match[AnyStr]: pass
def split(pattern: AnyStr, string: AnyStr, maxsplit: int = 0,
          flags: int = 0) -> List[AnyStr]: pass
def findall(pattern: AnyStr, string: AnyStr,
            flags: int = 0) -> List[AnyStr]: pass

# Return an iterator yielding match objects over all non-overlapping matches
# for the RE pattern in string. The string is scanned left-to-right, and
# matches are returned in the order found. Empty matches are included in the
# result unless they touch the beginning of another match.
def finditer(pattern: AnyStr, string: AnyStr,
             flags: int = 0) -> Iterator[Match[AnyStr]]: pass

@overload
def sub(pattern: AnyStr, repl: AnyStr, string: AnyStr, count: int = 0,
        flags: int = 0) -> AnyStr: pass
@overload
def sub(pattern: AnyStr, repl: Function[[Match[AnyStr]], AnyStr],
        string: AnyStr, count: int = 0, flags: int = 0) -> AnyStr: pass

@overload
def subn(pattern: AnyStr, repl: AnyStr, string: AnyStr, count: int = 0,
         flags: int = 0) -> Tuple[AnyStr, int]: pass
@overload
def subn(pattern: AnyStr, repl: Function[[Match[AnyStr]], AnyStr],
         string: AnyStr, count: int = 0,
         flags: int = 0) -> Tuple[AnyStr, int]: pass

def escape(string: AnyStr) -> AnyStr: pass

def purge() -> None: pass
