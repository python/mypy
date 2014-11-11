# builtins stub used in for statement test cases

from typing import typevar, Generic, Iterable, Iterator
from abc import abstractmethod, ABCMeta

t = typevar('t')

class object:
    def __init__(self) -> None: pass

class type: pass
class tuple: pass
class function: pass
class bool: pass
class int: pass # for convenience
class str: pass # for convenience

class list(Iterable[t], Generic[t]):
    def __iter__(self) -> Iterator[t]: pass
