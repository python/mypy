# builtins stub used in type-related test cases.

from typing import Generic, TypeVar, List

T = TypeVar('T')

class object:
    def __init__(self) -> None: pass
    def __str__(self) -> 'str': pass

class list(Generic[T]): pass

class type:
    __name__: str
    def mro(self) -> List['type']: pass

class tuple(Generic[T]): pass
class function: pass
class bool: pass
class int: pass
class str: pass
class unicode: pass
