# Stubs for re
# Ron Murawski <ron@horizonchess.com>
# 'bytes' support added by Jukka Lehtosalo

# based on: http://docs.python.org/3.2/library/re.html
# and http://hg.python.org/cpython/file/618ea5612e83/Lib/re.py

from typing import (
    Undefined, List, Iterator, overload, Function, Tuple, Sequence, Dict
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

class error(Exception): pass

class Match:
    pos = 0
    endpos = 0
    lastindex = 0
    lastgroup = ''
    string = ''
    
    # The regular expression object whose match() or search() method produced
    # this match instance.
    re = Undefined('Pattern')
    
    def expand(self, template: str) -> str: pass
    
    @overload
    def group(self, group1: int = 0) -> str: pass
    @overload
    def group(self, group1: str) -> str: pass
    @overload
    def group(self, group1: int, group2: int,
              *groups: int) -> Sequence[str]: pass
    @overload
    def group(self, group1: str, group2: str,
              *groups: str) -> Sequence[str]: pass
    
    def groups(self, default: str = None) -> Sequence[str]: pass
    def groupdict(self, default: str = None) -> Dict[str, str]: pass
    def start(self, group: int = 0) -> int: pass
    def end(self, group: int = 0) -> int: pass
    def span(self, group: int = 0) -> Tuple[int, int]: pass

class BytesMatch:
    pos = 0
    endpos = 0
    lastindex = 0
    lastgroup = b''
    string = b''
    
    # The regular expression object whose match() or search() method produced
    # this match instance.
    re = Undefined('BytesPattern')
    
    def expand(self, template: bytes) -> bytes: pass
    
    @overload
    def group(self, group1: int = 0) -> str: pass
    @overload
    def group(self, group1: str) -> str: pass
    @overload
    def group(self, group1: int, group2: int,
              *groups: int) -> Sequence[bytes]: pass
    @overload
    def group(self, group1: bytes, group2: bytes,
              *groups: bytes) -> Sequence[bytes]: pass
    
    def groups(self, default: bytes = None) -> Sequence[bytes]: pass
    def groupdict(self, default: bytes = None) -> Dict[bytes, bytes]: pass
    def start(self, group: int = 0) -> int: pass
    def end(self, group: int = 0) -> int: pass
    def span(self, group: int = 0) -> Tuple[int, int]: pass

# ----- re classes -----
class Pattern:
    flags = 0
    groupindex = 0
    groups = 0
    pattern = ''

    def search(self, string: str, pos: int = 0,
               endpos: int = -1) -> Match: pass
    def match(self, string: str, pos: int = 0, endpos: int = -1) -> Match: pass
    def split(self, string: str, maxsplit: int = 0) -> List[str]: pass
    def findall(self, string: str, pos: int = 0,
                endpos: int = -1) -> List[str]: pass
    def finditer(self, string: str, pos: int = 0,
                 endpos: int = -1) -> Iterator[Match]: pass
    
    @overload
    def sub(self, repl: str, string: str, count: int = 0) -> str: pass
    @overload
    def sub(self, repl: Function[[Match], str], string: str,
            count: int = 0) -> str: pass
    
    @overload
    def subn(self, repl: str, string: str, count: int = 0) -> Tuple[str,
                                                                    int]: pass
    @overload
    def subn(self, repl: Function[[Match], str], string: str,
             count: int = 0) -> Tuple[str, int]: pass

class BytesPattern:
    flags = 0
    groupindex = 0
    groups = 0
    pattern = b''

    def search(self, string: bytes, pos: int = 0,
               endpos: int = -1) -> BytesMatch: pass
    def match(self, string: bytes, pos: int = 0,
              endpos: int = -1) -> BytesMatch: pass
    def split(self, string: bytes, maxsplit: int = 0) -> List[bytes]: pass
    def findall(self, string: bytes, pos: int = 0,
                endpos: int = -1) -> List[bytes]: pass
    def finditer(self, string: bytes, pos: int = 0,
                 endpos: int = -1) -> Iterator[BytesMatch]: pass
    
    @overload
    def sub(self, repl: bytes, string: bytes, count: int = 0) -> bytes: pass
    @overload
    def sub(self, repl: Function[[BytesMatch], bytes], string: bytes,
            count: int = 0) -> bytes: pass
    
    @overload
    def subn(self, repl: bytes, string: bytes,
             count: int = 0) -> Tuple[bytes, int]: pass
    @overload
    def subn(self, repl: Function[[BytesMatch], bytes], string: bytes,
             count: int = 0) -> Tuple[bytes, int]: pass

@overload
def compile(pattern: str, flags: int = 0) -> Pattern: pass
@overload
def compile(pattern: bytes, flags: int = 0) -> BytesPattern: pass

@overload
def search(pattern: str, string: str, flags: int = 0) -> Match: pass
@overload
def search(pattern: bytes, string: bytes, flags: int = 0) -> BytesMatch: pass

@overload
def match(pattern: str, string: str, flags: int = 0) -> Match: pass
@overload
def match(pattern: bytes, string: bytes, flags: int = 0) -> BytesMatch: pass

@overload
def split(pattern: str, string: str, maxsplit: int = 0,
          flags: int = 0) -> List[str]: pass
@overload
def split(pattern: bytes, string: bytes, maxsplit: int = 0,
          flags: int = 0) -> List[bytes]: pass

@overload
def findall(pattern: str, string: str, flags: int = 0) -> List[str]: pass
@overload
def findall(pattern: bytes, string: bytes, flags: int = 0) -> List[bytes]: pass

# Return an iterator yielding match objects over all non-overlapping matches 
# for the RE pattern in string. The string is scanned left-to-right, and 
# matches are returned in the order found. Empty matches are included in the 
# result unless they touch the beginning of another match.
@overload
def finditer(pattern: str, string: str,
             flags: int = 0) -> Iterator[Match]: pass
@overload
def finditer(pattern: bytes, string: bytes,
             flags: int = 0) -> Iterator[BytesMatch]: pass

@overload
def sub(pattern: str, repl: str, string: str, count: int = 0,
        flags: int = 0) -> str: pass
@overload
def sub(pattern: str, repl: Function[[Match], str], string: str,
        count: int = 0, flags: int = 0) -> str: pass
@overload
def sub(pattern: bytes, repl: bytes, string: bytes, count: int = 0,
        flags: int = 0) -> bytes: pass
@overload
def sub(pattern: bytes, repl: Function[[BytesMatch], bytes], string: bytes,
        count: int = 0, flags: int = 0) -> bytes: pass

@overload
def subn(pattern: str, repl: str, string: str, count: int = 0,
         flags: int = 0) -> Tuple[str, int]: pass
@overload
def subn(pattern: str, repl: Function[[Match], str], string: str, 
         count: int = 0, flags: int = 0) -> Tuple[str, int]: pass
@overload
def subn(pattern: bytes, repl: bytes, string: bytes, count: int = 0, 
         flags: int = 0) -> Tuple[bytes, int]: pass
@overload
def subn(pattern: bytes, repl: Function[[BytesMatch], bytes],
         string: bytes, count: int = 0, flags: int = 0) -> Tuple[bytes,
                                                                 int]: pass

@overload
def escape(string: str) -> str: pass
@overload
def escape(string: bytes) -> bytes: pass

def purge() -> None: pass
