# Builtins stub used in tuple-related test cases.

from typing import Iterable, Iterator, TypeVar, Generic, Sequence, Any

Tco = TypeVar('Tco', covariant=True)

class object:
    def __init__(self): pass

class type:
    def __init__(self, *a) -> None: pass
    def __call__(self, *a) -> object: pass
class tuple(Sequence[Tco], Generic[Tco]):
    def __iter__(self) -> Iterator[Tco]: pass
    def __contains__(self, item: object) -> bool: pass
    def __getitem__(self, x: int) -> Tco: pass
    def count(self, obj: Any) -> int: pass
class function: pass

# We need int and slice for indexing tuples.
class int: pass
class slice: pass
class bool: pass
class str: pass # For convenience
class unicode: pass

T = TypeVar('T')

class list(Sequence[T], Generic[T]): pass
def isinstance(x: object, t: type) -> bool: pass

def sum(iterable: Iterable[T], start: T = None) -> T: pass

class BaseException: pass
