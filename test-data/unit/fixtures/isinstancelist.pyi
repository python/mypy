from typing import builtinclass, Iterable, Iterator, TypeVar, List, Mapping, overload, Tuple, Set, Union, Sequence, Generic

@builtinclass
class object:
    def __init__(self) -> None: pass

@builtinclass
class type:
    def __init__(self, x) -> None: pass

Tco = TypeVar('Tco', covariant=True)
class tuple(Sequence[Tco], Generic[Tco]):
    def __iter__(self) -> Iterator[Tco]: pass
    def __getitem__(self, x: int) -> Tco: pass

class function: pass

def isinstance(x: object, t: Union[type, Tuple]) -> bool: pass

@builtinclass
class int:
    def __add__(self, x: int) -> int: pass
@builtinclass
class bool(int): pass
@builtinclass
class str:
    def __add__(self, x: str) -> str: pass
    def __getitem__(self, x: int) -> str: pass

T = TypeVar('T')
KT = TypeVar('KT')
VT = TypeVar('VT')

class list(Iterable[T]):
    def __iter__(self) -> Iterator[T]: pass
    def __mul__(self, x: int) -> list[T]: pass
    def __setitem__(self, x: int, v: T) -> None: pass
    def __getitem__(self, x: int) -> T: pass
    def __add__(self, x: List[T]) -> T: pass

class dict(Iterable[KT], Mapping[KT, VT]):
    @overload
    def __init__(self, **kwargs: VT) -> None: pass
    @overload
    def __init__(self, arg: Iterable[Tuple[KT, VT]], **kwargs: VT) -> None: pass
    def __setitem__(self, k: KT, v: VT) -> None: pass
    def __iter__(self) -> Iterator[KT]: pass
    def update(self, a: Mapping[KT, VT]) -> None: pass

class set(Iterable[T]):
    def __iter__(self) -> Iterator[T]: pass
    def add(self, x: T) -> None: pass
    def discard(self, x: T) -> None: pass
    def update(self, x: Set[T]) -> None: pass
