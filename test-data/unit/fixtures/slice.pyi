# Builtins stub used in slicing test cases.
from typing import Generic, TypeVar, Mapping
T = TypeVar('T')
KT = TypeVar('KT')
VT = TypeVar('VT')

class object:
    def __init__(self): pass

class type: pass
class tuple(Generic[T]): pass
class dict(Mapping[KT, VT]): pass
class function: pass

class int: pass
class str: pass

class slice: pass
class ellipsis: pass
