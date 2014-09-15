# Stubs for heapq

# Based on http://docs.python.org/3.2/library/heapq.html

from typing import typevar, List, Iterable, Any, Function

_T = typevar('_T')

def heappush(heap: List[_T], item: _T) -> None: pass
def heappop(heap: List[_T]) -> _T: pass
def heappushpop(heap: List[_T], item: _T) -> _T: pass
def heapify(x: List[_T]) -> None: pass
def heapreplace(heap: List[_T], item: _T) -> _T: pass
def merge(*iterables: Iterable[_T]) -> Iterable[_T]: pass
def nlargest(n: int, iterable: Iterable[_T],
             key: Function[[_T], Any] = None) -> List[_T]: pass
def nsmallest(n: int, iterable: Iterable[_T],
              key: Function[[_T], Any] = None) -> List[_T]: pass
