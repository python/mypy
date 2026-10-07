# Builtins stub used in slicing test cases.
import types
from typing import Generic, TypeVar, Protocol
T = TypeVar('T')
_StartTco = TypeVar('_StartTco', covariant=True)
_StopTco = TypeVar('_StopTco', covariant=True)
_StepTco = TypeVar('_StepTco', covariant=True)

class SupportsIndex(Protocol):
    def __index__(self) -> int: ...

class object:
    def __init__(self): pass

class type: pass
class tuple(Generic[T]): pass
class function: pass

class int: pass
class str: pass

class slice(Generic[_StartTco, _StopTco, _StepTco]): pass
class dict: pass
class list(Generic[T]):
    def __getitem__(self, x: slice[SupportsIndex | None, SupportsIndex | None, SupportsIndex | None,]) -> list[T]: pass
