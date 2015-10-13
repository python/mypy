# Builtins stub used in list-related test cases.

from typing import TypeVar, Generic, builtinclass, Iterable, Iterator

T = TypeVar('T')

@builtinclass
class object:
    def __init__(self): pass

class type: pass

class list(Iterable[T], Generic[T]):
    def __iter__(self) -> Iterator[T]: pass
    def __mul__(self, x: int) -> list[T]: pass
    def __getitem__(self, x: int) -> T: pass

class tuple: pass
class function: pass
class int: pass
class str: pass
