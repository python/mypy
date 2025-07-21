# Builtins stub used in tuple-related test cases.
import collections
from typing import (
    Generic,
    Iterable,
    Iterator,
    Mapping,
    Self,
    Sequence,
    Tuple,
    TypeVar,
    overload,
)

import _typeshed

_T = TypeVar("_T")
_Tco = TypeVar('_Tco', covariant=True)
KT = TypeVar('KT')
VT = TypeVar('VT')

class object:
    def __init__(self) -> None: pass
    def __new__(cls) -> Self: ...
    def __eq__(self, other: object) -> bool: pass
    def __ne__(self, other: object) -> bool: pass

class type:
    __annotations__: Mapping[str, object]
    def __init__(self, *a: object) -> None: pass
    def __call__(self, *a: object) -> object: pass
class tuple(Sequence[_Tco], Generic[_Tco]):
    def __new__(cls: type[_T], iterable: Iterable[_Tco] = ...) -> _T: ...
    def __iter__(self) -> Iterator[_Tco]: pass
    def __len__(self) -> int: pass
    def __contains__(self, item: object) -> bool: pass
    @overload
    def __getitem__(self, x: int) -> _Tco: pass
    @overload
    def __getitem__(self, x: slice) -> Tuple[_Tco, ...]: ...
    def __mul__(self, n: int) -> Tuple[_Tco, ...]: pass
    def __rmul__(self, n: int) -> Tuple[_Tco, ...]: pass
    def __add__(self, x: Tuple[_Tco, ...]) -> Tuple[_Tco, ...]: pass
    def count(self, obj: object) -> int: pass
class function:
    __name__: str
class ellipsis: pass
class classmethod: pass
class staticmethod: pass
def callable(x: object) -> bool: pass

def len(__obj: object) -> int: ...

# We need int and slice for indexing tuples.
class int:
    def __neg__(self) -> 'int': pass
    def __pos__(self) -> 'int': pass
    def __add__(self, other: 'int') -> 'str': pass  # type: ignore[override]
    def __eq__(self, other: 'int') -> bool: pass  # type: ignore[override]
class float: pass
class slice: pass
class bool(int): pass
class str:
    def __add__(self, other: 'str') -> 'str': pass  # type: ignore[override]
    def __eq__(self, other: 'str') -> bool: pass  # type: ignore[override]
class bytes: pass
class bytearray: pass

class list(Sequence[_T], Generic[_T]):
    @overload
    def __getitem__(self, i: int) -> _T: ...
    @overload
    def __getitem__(self, s: slice) -> list[_T]: ...
    def __contains__(self, item: object) -> bool: ...
    def __iter__(self) -> Iterator[_T]: ...
    def __add__(self, x: list[_T]) -> list[_T]: ...

property = object() # Dummy definition.

def isinstance(x: object, t: type[object] | tuple[type[object], ...]) -> bool: pass

class BaseException: pass

class dict(Mapping[KT, VT]):
    def __iter__(self) -> Iterator[KT]: pass
