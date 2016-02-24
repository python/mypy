# Builtins stub used in tuple-related test cases.

from typing import Iterable, TypeVar, Generic, Sequence

Tco = TypeVar('Tco', covariant=True)

class object:
    def __init__(self): pass

class type: pass
class tuple(Sequence[Tco], Generic[Tco]):
    def __getitem__(self, x: int) -> Tco: pass
class function: pass

# We need int for indexing tuples.
class int: pass
class bool: pass
class str: pass # For convenience

T = TypeVar('T')

def sum(iterable: Iterable[T], start: T = None) -> T: pass

True = bool()
