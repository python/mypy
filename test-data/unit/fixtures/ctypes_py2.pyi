# Builtins stub used in ctypes-related test cases.

from typing import TypeVar, Generic, Mapping, Sequence

T = TypeVar('T')
K = TypeVar('K')
V = TypeVar('V')

class object:
    def __init__(self): pass

class type: pass

class dict(Mapping[K, V]): pass
class ellipsis: pass
class function: pass
class int: pass
class list(Sequence[T]): pass
class slice: pass
class str: pass
class tuple(Generic[T]): pass
class unicode: pass
