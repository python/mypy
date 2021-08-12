# builtins stub used in type-related test cases.

from typing import Generic, TypeVar, List, Union, Mapping

T = TypeVar('T')
KT = TypeVar('KT')
VT = TypeVar('VT')

class object:
    def __init__(self) -> None: pass
    def __str__(self) -> 'str': pass

class list(Generic[T]): pass
class dict(Mapping[KT, VT]): pass

class type(Generic[T]):
    __name__: str
    def __or__(self, other: Union[type, None]) -> type: pass
    def mro(self) -> List['type']: pass

class tuple(Generic[T]): pass
class function: pass
class bool: pass
class int: pass
class str: pass
class unicode: pass
