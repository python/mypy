# builtins stub used in boolean-related test cases.
from typing import Generic, TypeVar, Mapping
import sys
T = TypeVar('T')
KT = TypeVar('KT')
VT = TypeVar('VT')

class object:
    def __init__(self) -> None: pass

class type: pass
class tuple(Generic[T]): pass
class function: pass
class bool: pass
class int: pass
class str: pass
class unicode: pass
class ellipsis: pass
class dict(Mapping[KT, VT]): pass
