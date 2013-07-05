# Stubs for re
# Ron Murawski <ron@horizonchess.com>
# 'bytes' support added by Jukka Lehtosalo

# based on: http://docs.python.org/2.7/library/re.html

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

class UnicodeMatch:
    pos = 0
    endpos = 0
    lastindex = 0
    lastgroup = u''
    string = u''
    
    # The regular expression object whose match() or search() method produced
    # this match instance.
    re = Undefined('UnicodePattern')
    
    def expand(self, template: unicode) -> unicode: pass
    
    @overload
    def group(self, group1: int = 0) -> unicode: pass
    @overload
    def group(self, group1: unicode) -> unicode: pass
    @overload
    def group(self, group1: int, group2: int,
              *groups: int) -> Sequence[unicode]: pass
    @overload
    def group(self, group1: unicode, group2: unicode,
              *groups: unicode) -> Sequence[unicode]: pass
    
    def groups(self, default: unicode = None) -> Sequence[unicode]: pass
    def groupdict(self, default: unicode = None) -> Dict[unicode,
                                                         unicode]: pass
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

class UnicodePattern:
    flags = 0
    groupindex = 0
    groups = 0
    pattern = u''

    def search(self, string: unicode, pos: int = 0,
               endpos: int = -1) -> UnicodeMatch: pass
    def match(self, string: unicode, pos: int = 0,
              endpos: int = -1) -> UnicodeMatch: pass
    def split(self, string: unicode, maxsplit: int = 0) -> List[unicode]: pass
    def findall(self, string: unicode, pos: int = 0,
                endpos: int = -1) -> List[unicode]: pass
    def finditer(self, string: unicode, pos: int = 0,
                 endpos: int = -1) -> Iterator[UnicodeMatch]: pass
    
    @overload
    def sub(self, repl: unicode, string: unicode,
            count: int = 0) -> unicode: pass
    @overload
    def sub(self, repl: Function[[UnicodeMatch], unicode], string: unicode,
            count: int = 0) -> unicode: pass
    
    @overload
    def subn(self, repl: unicode, string: unicode,
             count: int = 0) -> Tuple[unicode, int]: pass
    @overload
    def subn(self, repl: Function[[UnicodeMatch], unicode], string: unicode,
             count: int = 0) -> Tuple[unicode, int]: pass

@overload
def compile(pattern: str, flags: int = 0) -> Pattern: pass
@overload
def compile(pattern: unicode, flags: int = 0) -> UnicodePattern: pass

@overload
def search(pattern: str, string: str, flags: int = 0) -> Match: pass
@overload
def search(pattern: unicode, string: unicode,
           flags: int = 0) -> UnicodeMatch: pass

@overload
def match(pattern: str, string: str, flags: int = 0) -> Match: pass
@overload
def match(pattern: unicode, string: unicode,
          flags: int = 0) -> UnicodeMatch: pass

@overload
def split(pattern: str, string: str, maxsplit: int = 0,
          flags: int = 0) -> List[str]: pass
@overload
def split(pattern: unicode, string: unicode, maxsplit: int = 0,
          flags: int = 0) -> List[unicode]: pass

@overload
def findall(pattern: str, string: str, flags: int = 0) -> List[str]: pass
@overload
def findall(pattern: unicode, string: unicode,
            flags: int = 0) -> List[unicode]: pass

# Return an iterator yielding match objects over all non-overlapping matches 
# for the RE pattern in string. The string is scanned left-to-right, and 
# matches are returned in the order found. Empty matches are included in the 
# result unless they touch the beginning of another match.
@overload
def finditer(pattern: str, string: str,
             flags: int = 0) -> Iterator[Match]: pass
@overload
def finditer(pattern: unicode, string: unicode,
             flags: int = 0) -> Iterator[UnicodeMatch]: pass

@overload
def sub(pattern: str, repl: str, string: str, count: int = 0,
        flags: int = 0) -> str: pass
@overload
def sub(pattern: str, repl: Function[[Match], str], string: str,
        count: int = 0, flags: int = 0) -> str: pass
@overload
def sub(pattern: unicode, repl: unicode, string: unicode, count: int = 0,
        flags: int = 0) -> unicode: pass
@overload
def sub(pattern: unicode, repl: Function[[UnicodeMatch], unicode],
        string: unicode, count: int = 0, flags: int = 0) -> unicode: pass

@overload
def subn(pattern: str, repl: str, string: str, count: int = 0,
         flags: int = 0) -> Tuple[str, int]: pass
@overload
def subn(pattern: str, repl: Function[[Match], str], string: str, 
         count: int = 0, flags: int = 0) -> Tuple[str, int]: pass
@overload
def subn(pattern: unicode, repl: unicode, string: unicode, count: int = 0, 
         flags: int = 0) -> Tuple[unicode, int]: pass
@overload
def subn(pattern: unicode, repl: Function[[UnicodeMatch], unicode],
         string: unicode, count: int = 0, flags: int = 0) -> Tuple[unicode,
                                                                   int]: pass

@overload
def escape(string: str) -> str: pass
@overload
def escape(string: unicode) -> unicode: pass

def purge() -> None: pass
