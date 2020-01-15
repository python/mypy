# Builtins stub used in dictionary-related test cases.

from typing import (
    TypeVar, Generic, Iterable, Iterator, Mapping, Tuple, overload, Optional, Union, Sequence
)

T = TypeVar('T')
KT = TypeVar('KT')
VT = TypeVar('VT')

class object:
    def __init__(self) -> None: pass
    def __init_subclass__(cls) -> None: pass
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
    def update(self, a: Mapping[KT, VT]) -> None: pass
    @overload
    def get(self, k: KT) -> Optional[VT]: pass
    @overload
    def get(self, k: KT, default: Union[KT, T]) -> Union[VT, T]: pass
    def __len__(self) -> int: ...

class int: # for convenience
    def __add__(self, x: int) -> int: pass

class str: pass # for keyword argument key type
class unicode: pass # needed for py2 docstrings

class list(Sequence[T]): # needed by some test cases
    def __getitem__(self, x: int) -> T: pass
    def __iter__(self) -> Iterator[T]: pass
    def __mul__(self, x: int) -> list[T]: pass
    def __contains__(self, item: object) -> bool: pass
    def append(self, item: T) -> None: pass

class tuple(Generic[T]): pass
class function: pass
class float: pass
class bool(int): pass

class ellipsis: pass
def isinstance(x: object, t: Union[type, Tuple[type, ...]]) -> bool: pass
class BaseException: pass
