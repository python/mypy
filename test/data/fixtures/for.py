# builtins stub used in for statement test cases

from typing import typevar, Generic
from abc import abstractmethod, ABCMeta

t = typevar('t')

class object:
    def __init__(self) -> None: pass
    
class type: pass
class bool: pass
class str: pass

class Iterable(AbstractGeneric[t]):
    @abstractmethod
    def __iter__(self) -> 'Iterator[t]': pass

class Iterator(Iterable[t], Generic[t]):
    @abstractmethod
    def __next__(self) -> t: pass

class list(Iterable[t], Generic[t]):
    def __iter__(self) -> Iterator[t]: pass

class tuple: pass
