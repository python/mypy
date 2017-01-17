# Builtins stub used in dictionary-related test cases.

from typing import TypeVar, Generic, Iterable, Iterator, Mapping, Tuple, overload

T = TypeVar('T')
KT = TypeVar('KT')
VT = TypeVar('VT')

class object:
    def __init__(self) -> None: pass

class type: pass

class dict(Iterable[KT], Mapping[KT, VT], Generic[KT, VT]):
    @overload
    def __init__(self, **kwargs: VT) -> None: pass
    @overload
    def __init__(self, arg: Iterable[Tuple[KT, VT]], **kwargs: VT) -> None: pass
    def __setitem__(self, k: KT, v: VT) -> None: pass
    def __iter__(self) -> Iterator[KT]: pass
    def update(self, a: Mapping[KT, VT]) -> None: pass

class int: # for convenience
    def __add__(self, x: int) -> int: pass

class str: pass # for keyword argument key type
class unicode: pass # needed for py2 docstrings

class list(Iterable[T], Generic[T]): # needed by some test cases
    def __iter__(self) -> Iterator[T]: pass
    def __mul__(self, x: int) -> list[T]: pass

class tuple: pass
class function: pass
class float: pass
