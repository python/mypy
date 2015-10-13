from typing import Sequence, TypeVar

_T = TypeVar('_T')

def insort_left(a: Sequence[_T], x: _T, lo: int = 0, hi: int = None): pass
def insort_right(a: Sequence[_T], x: _T, lo: int = 0, hi: int = None): pass

def bisect_left(a: Sequence[_T], x: _T, lo: int = 0, hi: int = None): pass
def bisect_right(a: Sequence[_T], x: _T, lo: int = 0, hi: int = None): pass

insort = insort_right
bisect = bisect_right
