# Builtins stub used in dictionary-related test cases.

from typing import TypeVar, Generic, Iterable, Iterator, Tuple, overload

T = TypeVar('T')
KT = TypeVar('KT')
VT = TypeVar('VT')

class object:
    def __init__(self) -> None: pass

class type: pass

class dict(Iterable[KT], Generic[KT, VT]):
    @overload
    def __init__(self, **kwargs: VT) -> None: pass
    @overload
    def __init__(self, arg: Iterable[Tuple[KT, VT]], **kwargs: VT) -> None: pass
    def __setitem__(self, k: KT, v: VT) -> None: pass
    def __iter__(self) -> Iterator[KT]: pass
    def update(self, a: 'dict[KT, VT]') -> None: pass

class int: pass # for convenience

class str: pass # for keyword argument key type

class list(Iterable[T], Generic[T]): # needed by some test cases
    def __iter__(self) -> Iterator[T]: pass
    def __mul__(self, x: int) -> list[T]: pass

class tuple: pass
class function: pass
class float: pass
