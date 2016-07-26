# Builtins stub used in tuple-related test cases.

from typing import Iterable, Iterator, TypeVar, Generic, Sequence, overload

Tco = TypeVar('Tco', covariant=True)

class object:
    def __init__(self): pass

class type:
    def __init__(self, *a) -> None: pass
    def __call__(self, *a) -> object: pass
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

class list(Iterable[T], Generic[T]):
    @overload
    def __init__(self) -> None: pass
    @overload
    def __init__(self, x: Iterable[T]) -> None: pass
    def __iter__(self) -> Iterator[T]: pass
    def __mul__(self, x: int) -> list[T]: pass
    def __getitem__(self, x: int) -> T: pass
    def append(self, x: T) -> None: pass
    def extend(self, x: Iterable[T]) -> None: pass
