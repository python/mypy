# Stubs for difflib

# Based on https://docs.python.org/2.7/library/difflib.html

from typing import (typevar, Function, Iterable, List, NamedTuple, Sequence,
                    Tuple)

_T = typevar('_T')

Match = NamedTuple('Match', [('a', Sequence[_T]), ('b', Sequence[_T]),
                             ('size', int)])

class SequenceMatcher:
    def __init__(self, isjunk: Function[[_T], bool]=None,
                 a: Sequence[_T]='', b: Sequence[_T]='',
                 autojunk: bool=True) -> None: pass
    def set_seqs(self, a: Sequence[_T], b: Sequence[_T]) -> None: pass
    def set_seq1(self, a: Sequence[_T]) -> None: pass
    def set_seq2(self, b: Sequence[_T]) -> None: pass
    def find_longest_match(self, alo: int, ahi: int, blo: int,
                           bhi: int) -> Match: pass
    def get_matching_blocks(self) -> List[Match]: pass
    def get_opcodes(self) -> List[Tuple[str, int, int, int, int]]: pass
    def get_grouped_opcodes(self, n: int=3
                            ) -> Iterable[Tuple[str, int, int, int, int]]: pass
    def ratio(self) -> float: pass
    def quick_ratio(self) -> float: pass
    def real_quick_ratio(self) -> float: pass

def get_close_matches(word: Sequence[_T], possibilities: List[Sequence[_T]],
                      n: int=3, cutoff: float=0.6): pass

class Differ:
    def __init__(self, linejunk: Function[[str], bool]=None,
                 charjunk: Function[[str], bool]=None) -> None: pass
    def compare(self, a: Sequence[str],
                b: Sequence[str]) -> Iterable[str]: pass

def IS_LINE_JUNK(str) -> bool: pass
def IS_CHARACTER_JUNK(str) -> bool: pass
def unified_diff(a: Sequence[str], b: Sequence[str], fromfile: str='',
                 tofile: str='', fromfiledate: str='', tofiledate: str='',
                 n: int=3, lineterm: str='\n') -> Iterable[str]: pass
def context_diff(a: Sequence[str], b: Sequence[str], fromfile: str='',
                 tofile: str='', fromfiledate: str='', tofiledate: str='',
                 n: int=3, lineterm: str='\n') -> Iterable[str]: pass
def ndiff(a: Sequence[str], b: Sequence[str],
          linejunk: Function[[str], bool]=None,
          charjunk: Function[[str], bool]=IS_CHARACTER_JUNK
          ) -> Iterable[str]: pass

class HtmlDiff(object):
    def __init__(self, tabsize: int=8, wrapcolumn: int=None,
                 linejunk: Function[[str], bool]=None,
                 charjunk: Function[[str], bool]=IS_CHARACTER_JUNK
                 ) -> None: pass
    def make_file(self, fromlines: Sequence[str], tolines: Sequence[str],
                  fromdesc: str='', todesc: str='', context: bool=False,
                  numlines: int=5) -> str: pass
    def make_table(self, fromlines: Sequence[str], tolines: Sequence[str],
                   fromdesc: str='', todesc: str='', context: bool=False,
                   numlines: int=5) -> str: pass

def restore(delta: Iterable[str], which: int) -> Iterable[int]: pass
