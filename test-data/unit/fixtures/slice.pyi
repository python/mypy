# Builtins stub used in slicing test cases.
from typing import Generic, TypeVar
T = TypeVar('T')

class object:
    def __init__(self): pass

class type: pass
class tuple(Generic[T]): pass
class function: pass

class int: pass
class str: pass

class slice: pass
class ellipsis: pass
class dict: pass
class list(Generic[T]):
    def __getitem__(self, x: slice) -> list[T]: pass
