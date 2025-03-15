# Builtins stub used in list-related test cases.

from typing import TypeVar, Generic, Iterable, Iterator, Sequence, overload

T = TypeVar('T')

class object:
    def __init__(self) -> None: pass
    def __eq__(self, other: object) -> bool: pass

class type: pass
class ellipsis: pass

class list(Sequence[T]):
    @overload
    def __init__(self) -> None: pass
    @overload
    def __init__(self, x: Iterable[T]) -> None: pass
    def __iter__(self) -> Iterator[T]: pass
    def __len__(self) -> int: pass
    def __contains__(self, item: object) -> bool: pass
    def __add__(self, x: list[T]) -> list[T]: pass
    def __mul__(self, x: int) -> list[T]: pass
    def __getitem__(self, x: int) -> T: pass
    def __setitem__(self, x: int, v: T) -> None: pass
    def append(self, x: T) -> None: pass
    def extend(self, x: Iterable[T]) -> None: pass

class tuple(Generic[T]): pass
class function: pass
class int:
    def __bool__(self) -> bool: pass
class float:
    def __bool__(self) -> bool: pass
class str:
    def __len__(self) -> bool: pass
class bool(int): pass

property = object() # Dummy definition.

class dict: pass
