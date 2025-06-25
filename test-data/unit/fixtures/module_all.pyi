from typing import Generic, Sequence, TypeVar
from types import ModuleType

_T = TypeVar('_T')

class object:
    def __init__(self) -> None: pass
class type: pass
class function: pass
class int: pass
class str: pass
class bool: pass
class list(Generic[_T], Sequence[_T]):
    def append(self, x: _T): pass
    def extend(self, x: Sequence[_T]): pass
    def remove(self, x: _T): pass
    def __add__(self, rhs: Sequence[_T]) -> list[_T]: pass
class tuple(Generic[_T]): pass
class ellipsis: pass
class dict: pass
