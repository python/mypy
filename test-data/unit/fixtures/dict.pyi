# Builtins stub used in dictionary-related test cases (stripped down).
#
# NOTE: Use dict-full.pyi if you need more builtins instead of adding here,
#       if feasible.

from _typeshed import SupportsKeysAndGetItem
import _typeshed
from typing import (
    TypeVar, Generic, Iterable, Iterator, Mapping, Tuple, overload, Optional, Union, Sequence,
    Self,
)

T = TypeVar('T')
T2 = TypeVar('T2')
KT = TypeVar('KT')
VT = TypeVar('VT')

class object:
    def __init__(self) -> None: pass
    def __eq__(self, other: object) -> bool: pass

class type: pass

class dict(Mapping[KT, VT]):
    @overload
    def __init__(self, **kwargs: VT) -> None: pass
    @overload
    def __init__(self, arg: Iterable[Tuple[KT, VT]], **kwargs: VT) -> None: pass
    def __getitem__(self, key: KT) -> VT: pass
    def __setitem__(self, k: KT, v: VT) -> None: pass
    def __iter__(self) -> Iterator[KT]: pass
    def __contains__(self, item: object) -> int: pass
    def update(self, a: SupportsKeysAndGetItem[KT, VT]) -> None: pass
    @overload
    def get(self, k: KT) -> Optional[VT]: pass
    @overload
    def get(self, k: KT, default: Union[VT, T]) -> Union[VT, T]: pass
    def __len__(self) -> int: ...

class int: # for convenience
    def __add__(self, x: Union[int, complex]) -> int: pass
    def __radd__(self, x: int) -> int: pass
    def __sub__(self, x: Union[int, complex]) -> int: pass

class str: pass # for keyword argument key type
class bytes: pass

class list(Sequence[T]): # needed by some test cases
    def __getitem__(self, x: int) -> T: pass
    def __iter__(self) -> Iterator[T]: pass
    def __mul__(self, x: int) -> list[T]: pass
    def __contains__(self, item: object) -> bool: pass
    def append(self, item: T) -> None: pass

class tuple(Generic[T]): pass
class function: pass
class float: pass
class complex: pass
class bool(int): pass
class ellipsis: pass
class BaseException: pass

def isinstance(x: object, t: Union[type, Tuple[type, ...]]) -> bool: pass
def iter(__iterable: Iterable[T]) -> Iterator[T]: pass
