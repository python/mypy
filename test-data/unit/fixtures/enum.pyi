# Minimal set of builtins required to work with Enums
from typing import TypeVar, Generic, Iterator, Sequence, overload, Iterable

T = TypeVar('T')

class object:
    def __init__(self): pass

class type: pass
class tuple(Generic[T]):
    def __getitem__(self, x: int) -> T: pass

class int: pass
class str:
    def __len__(self) -> int: pass
    def __iter__(self) -> Iterator[str]: pass

class dict: pass
class ellipsis: pass

class list(Sequence[T]):
    @overload
    def __init__(self) -> None: pass
    @overload
    def __init__(self, x: Iterable[T]) -> None: pass
