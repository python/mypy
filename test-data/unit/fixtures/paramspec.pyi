# builtins stub for paramspec-related test cases

from typing import (
    Sequence, Generic, TypeVar, Iterable, Iterator, Tuple, Mapping, Optional, Union, Type, overload,
    Protocol
)

T = TypeVar("T")
T_co = TypeVar('T_co', covariant=True)
KT = TypeVar("KT")
VT = TypeVar("VT")

class object:
    def __init__(self) -> None: pass

class function: pass
class ellipsis: pass

class type:
    def __init__(self, *a: object) -> None: pass
    def __call__(self, *a: object) -> object: pass

class list(Sequence[T], Generic[T]):
    @overload
    def __getitem__(self, i: int) -> T: ...
    @overload
    def __getitem__(self, s: slice) -> list[T]: ...
    def __contains__(self, item: object) -> bool: ...
    def __iter__(self) -> Iterator[T]: ...

# We need int and slice for indexing tuples.
class int:
    def __neg__(self) -> 'int': pass

class bool(int): pass
class float: pass
class slice: pass
class str: pass # for keyword argument key type
class bytes: pass

class tuple(Sequence[T_co], Generic[T_co]):
    def __new__(cls: Type[T], iterable: Iterable[T_co] = ...) -> T: pass
    def __iter__(self) -> Iterator[T_co]: pass
    def __contains__(self, item: object) -> bool: pass
    def __getitem__(self, x: int) -> T_co: pass
    def __mul__(self, n: int) -> Tuple[T_co, ...]: pass
    def __rmul__(self, n: int) -> Tuple[T_co, ...]: pass
    def __add__(self, x: Tuple[T_co, ...]) -> Tuple[T_co, ...]: pass
    def __len__(self) -> int: ...
    def count(self, obj: object) -> int: pass

class _ItemsView(Iterable[Tuple[KT, VT]]): pass

class dict(Mapping[KT, VT]):
    @overload
    def __init__(self, **kwargs: VT) -> None: pass
    @overload
    def __init__(self, arg: Iterable[Tuple[KT, VT]], **kwargs: VT) -> None: pass
    def __getitem__(self, key: KT) -> VT: pass
    def __setitem__(self, k: KT, v: VT) -> None: pass
    def __iter__(self) -> Iterator[KT]: pass
    def __contains__(self, item: object) -> int: pass
    def update(self, a: Mapping[KT, VT]) -> None: pass
    @overload
    def get(self, k: KT) -> Optional[VT]: pass
    @overload
    def get(self, k: KT, default: Union[KT, T]) -> Union[VT, T]: pass
    def __len__(self) -> int: pass
    def pop(self, k: KT) -> VT: pass
    def items(self) -> _ItemsView[KT, VT]: pass

def isinstance(x: object, t: type) -> bool: pass

class _Sized(Protocol):
    def __len__(self) -> int: pass

def len(x: _Sized) -> int: pass
