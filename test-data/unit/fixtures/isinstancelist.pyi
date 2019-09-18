from typing import (
    Iterable, Iterator, TypeVar, List, Mapping, overload, Tuple, Set, Union, Generic, Sequence
)

class object:
    def __init__(self) -> None: pass
    def __eq__(self, other: object) -> bool: pass

class type:
    def __init__(self, x) -> None: pass

class function: pass
class ellipsis: pass
class classmethod: pass

def isinstance(x: object, t: Union[type, Tuple]) -> bool: pass
def issubclass(x: object, t: Union[type, Tuple]) -> bool: pass

class int:
    def __add__(self, x: int) -> int: pass
class float: pass
class bool(int): pass
class str:
    def __add__(self, x: str) -> str: pass
    def __getitem__(self, x: int) -> str: pass

T = TypeVar('T')
KT = TypeVar('KT')
VT = TypeVar('VT')

class tuple(Generic[T]):
    def __len__(self) -> int: pass

class list(Sequence[T]):
    def __iter__(self) -> Iterator[T]: pass
    def __mul__(self, x: int) -> list[T]: pass
    def __setitem__(self, x: int, v: T) -> None: pass
    def __getitem__(self, x: int) -> T: pass
    def __add__(self, x: List[T]) -> T: pass
    def __contains__(self, item: object) -> bool: pass

class dict(Mapping[KT, VT]):
    @overload
    def __init__(self, **kwargs: VT) -> None: pass
    @overload
    def __init__(self, arg: Iterable[Tuple[KT, VT]], **kwargs: VT) -> None: pass
    def __setitem__(self, k: KT, v: VT) -> None: pass
    def __iter__(self) -> Iterator[KT]: pass
    def update(self, a: Mapping[KT, VT]) -> None: pass

class set(Generic[T]):
    def __iter__(self) -> Iterator[T]: pass
    def add(self, x: T) -> None: pass
    def discard(self, x: T) -> None: pass
    def update(self, x: Set[T]) -> None: pass
    def pop(self) -> T: pass
