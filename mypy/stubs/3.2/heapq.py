# Stubs for heapq

# Based on http://docs.python.org/3.2/library/heapq.html

from typing import typevar, List, Iterable, Any, Function

T = typevar('T')

def heappush(heap: List[T], item: T) -> None: pass
def heappop(heap: List[T]) -> T: pass
def heappushpop(heap: List[T], item: T) -> T: pass
def heapify(x: List[T]) -> None: pass
def heapreplace(heap: List[T], item: T) -> T: pass
def merge(*iterables: Iterable[T]) -> Iterable[T]: pass
def nlargest(n: int, iterable: Iterable[T],
             key: Function[[T], Any] = None) -> List[T]: pass
def nsmallest(n: int, iterable: Iterable[T],
              key: Function[[T], Any] = None) -> List[T]: pass
