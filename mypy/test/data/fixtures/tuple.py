# Builtins stub used in tuple-related test cases.

from typing import Iterable, TypeVar, Generic

Tco = TypeVar('Tco')

class object:
    def __init__(self): pass

class type: pass
class tuple(Generic[Tco]): pass
class function: pass

# We need int for indexing tuples.
class int: pass
class str: pass # For convenience

T = TypeVar('T')

def sum(iterable: Iterable[T], start: T = None) -> T: pass
