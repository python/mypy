# Builtins stub used in slicing test cases.
from typing import Generic, TypeVar, Iterator, Iterable
T = TypeVar('T')

class object:
    def __init__(self): pass

class type: pass
class tuple(Generic[T]): pass
class function: pass

class int: pass
class str: pass

class slice: pass
class ellipsis: pass

class list(Iterable[T]):
    def __iter__(self) -> Iterator[T]: pass
class dict: pass
