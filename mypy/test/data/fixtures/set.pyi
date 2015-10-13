# Builtins stub used in set-related test cases.

from typing import TypeVar, Generic, Iterator, Iterable

T = TypeVar('T')

class object:
    def __init__(self) -> None: pass

class type: pass
class tuple: pass
class function: pass

class int: pass
class str: pass

class set(Iterable[T], Generic[T]):
    def __iter__(self) -> Iterator[T]: pass
