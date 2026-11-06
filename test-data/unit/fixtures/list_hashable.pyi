# Builtins stub used in list tests that need hashability information.

import types
from typing import Any, ClassVar, Generic, Iterable, Iterator, MutableSequence, TypeVar, overload

T = TypeVar('T')

class object:
    def __init__(self) -> None: pass
    def __eq__(self, other: object) -> bool: pass
    def __hash__(self) -> int: pass

class type: pass

class list(MutableSequence[T]):
    __hash__: ClassVar[None]  # type: ignore[assignment]
    @overload
    def __init__(self) -> None: pass
    @overload
    def __init__(self, x: Iterable[T]) -> None: pass
    def __iter__(self) -> Iterator[T]: pass
    def __len__(self) -> int: pass
    def __contains__(self, item: object) -> bool: pass
    def __add__(self, x: list[T]) -> list[T]: pass
    def __mul__(self, x: int) -> list[T]: pass
    def __getitem__(self, x: Any) -> T: pass
    def __setitem__(self, x: Any, v: T) -> None: pass
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

K = TypeVar('K')
V = TypeVar('V')

class dict(Generic[K, V]):
    __hash__: ClassVar[None]  # type: ignore[assignment]
