# Builtins stub used in set-related test cases.

from typing import TypeVar, Generic, Iterator, Iterable, Set

T = TypeVar('T')

class object:
    def __init__(self) -> None: pass
    def __eq__(self, other): pass

class type: pass
class tuple(Generic[T]): pass
class function: pass

class int: pass
class str: pass
class bool: pass
class ellipsis: pass

class set(Iterable[T], Generic[T]):
    def __init__(self, iterable: Iterable[T] = ...) -> None: ...
    def __iter__(self) -> Iterator[T]: pass
    def __contains__(self, item: object) -> bool: pass
    def __ior__(self, x: Set[T]) -> None: pass
    def add(self, x: T) -> None: pass
    def discard(self, x: T) -> None: pass
    def update(self, x: Set[T]) -> None: pass

class dict: pass
