from typing import Any, Dict, Generic, TypeVar, Sequence
from types import ModuleType

T = TypeVar('T')
S = TypeVar('S')

class list(Generic[T], Sequence[T]): pass

class object:
    def __init__(self) -> None: pass
class type: pass
class function: pass
class int: pass
class str: pass
class bool: pass
class tuple(Generic[T]): pass
class dict(Generic[T, S]): pass
class ellipsis: pass

classmethod = object()
staticmethod = object()
property = object()
def hasattr(x: object, name: str) -> bool: pass
