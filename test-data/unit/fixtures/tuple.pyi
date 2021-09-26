# Builtins stub used in tuple-related test cases.

from typing import Iterable, Iterator, TypeVar, Generic, Sequence, Any, overload, Tuple, Mapping, Type
from typing import Iterable, Iterator, TypeVar, Generic, Sequence, Any, overload, Tuple, Type

T = TypeVar("T")
KT = TypeVar('KT')
VT = TypeVar('VT')
Tco = TypeVar('Tco', covariant=True)

class object:
    def __init__(self) -> None: pass

class type:
    def __init__(self, *a: object) -> None: pass
    def __call__(self, *a: object) -> object: pass
class tuple(Sequence[Tco], Generic[Tco]):
    def __new__(cls: Type[T], iterable: Iterable[Tco] = ...) -> T: ...
    def __iter__(self) -> Iterator[Tco]: pass
    def __contains__(self, item: object) -> bool: pass
    def __getitem__(self, x: int) -> Tco: pass
    def __mul__(self, n: int) -> Tuple[Tco, ...]: pass
    def __rmul__(self, n: int) -> Tuple[Tco, ...]: pass
    def __add__(self, x: Tuple[Tco, ...]) -> Tuple[Tco, ...]: pass
    def count(self, obj: object) -> int: pass
class function: pass
class ellipsis: pass

# We need int and slice for indexing tuples.
class int:
    def __neg__(self) -> 'int': pass
class float: pass
class slice: pass
class bool(int): pass
class str: pass # For convenience
class bytes: pass
class unicode: pass

class list(Sequence[T], Generic[T]):
    @overload
    def __getitem__(self, i: int) -> T: ...
    @overload
    def __getitem__(self, s: slice) -> list[T]: ...
    def __contains__(self, item: object) -> bool: ...
    def __iter__(self) -> Iterator[T]: ...

class dict(Mapping[KT, VT]):
    def __iter__(self) -> Iterator[KT]: pass


def isinstance(x: object, t: type) -> bool: pass

def sum(iterable: Iterable[T], start: T = None) -> T: pass

class BaseException: pass
