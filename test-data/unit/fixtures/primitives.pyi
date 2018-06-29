# builtins stub with non-generic primitive types
from typing import Generic, TypeVar
T = TypeVar('T')

class object:
    def __init__(self) -> None: pass
    def __str__(self) -> str: pass

class type:
    def __init__(self, x) -> None: pass

class int:
    def __add__(self, i: int) -> int: pass
class float:
    def __float__(self) -> float: pass
class complex: pass
class bool(int): pass
class str:
    def __add__(self, s: str) -> str: pass
    def format(self, *args) -> str: pass
class bytes: pass
class bytearray: pass
class tuple(Generic[T]): pass
class function: pass
