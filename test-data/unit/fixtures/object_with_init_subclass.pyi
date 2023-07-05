from typing import Sequence, Iterator, TypeVar, Mapping, Iterable, Optional, Union, overload, Tuple, Generic, List

class object:
    def __init__(self) -> None: ...
    def __init_subclass__(cls) -> None: ...

T = TypeVar('T')
KT = TypeVar('KT')
VT = TypeVar('VT')
# copy pasted from primitives.pyi
class type:
    def __init__(self, x) -> None: pass

class int:
    # Note: this is a simplification of the actual signature
    def __init__(self, x: object = ..., base: int = ...) -> None: pass
    def __add__(self, i: int) -> int: pass
class float:
    def __float__(self) -> float: pass
class complex: pass
class bool(int): pass
class str(Sequence[str]):
    def __add__(self, s: str) -> str: pass
    def __iter__(self) -> Iterator[str]: pass
    def __contains__(self, other: object) -> bool: pass
    def __getitem__(self, item: int) -> str: pass
    def format(self, *args) -> str: pass
class bytes(Sequence[int]):
    def __iter__(self) -> Iterator[int]: pass
    def __contains__(self, other: object) -> bool: pass
    def __getitem__(self, item: int) -> int: pass
class bytearray: pass
class tuple(Generic[T]): pass
class function: pass
class ellipsis: pass

# copy-pasted from list.pyi
class list(Sequence[T]):
    def __iter__(self) -> Iterator[T]: pass
    def __mul__(self, x: int) -> list[T]: pass
    def __setitem__(self, x: int, v: T) -> None: pass
    def __getitem__(self, x: int) -> T: pass
    def __add__(self, x: List[T]) -> T: pass
    def __contains__(self, item: object) -> bool: pass

# copy-pasted from dict.pyi
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
