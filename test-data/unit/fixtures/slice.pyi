# Builtins stub used in slicing test cases.
from typing import Generic, TypeVar, Protocol
T = TypeVar('T')
_Tco = TypeVar('_Tco', covariant=True)

class SupportsIndex(Protocol):
    def __index__(self) -> int: ...

class object:
    def __init__(self): pass

class type: pass
class tuple(Generic[T]): pass
class function: pass

class int: pass
class str: pass

class slice(Generic[_Tco]): pass
class ellipsis: pass
class dict: pass
class list(Generic[T]):
    def __getitem__(self, x: slice[SupportsIndex | None]) -> list[T]: pass
