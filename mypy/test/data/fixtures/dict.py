# Builtins stub used in dictionary-related test cases.

from typing import TypeVar, Generic, Iterable, Iterator

T = TypeVar('T')
S = TypeVar('S')

class object:
    def __init__(self) -> None: pass

class type: pass

class dict(Generic[T, S]): pass
class int: pass # for convenience
class str: pass # for keyword argument key type
class list(Iterable[T], Generic[T]): # needed by some test cases
    def __iter__(self) -> Iterator[T]: pass
    def __mul__(self, x: int) -> list[T]: pass

class tuple: pass
class function: pass
class float: pass
