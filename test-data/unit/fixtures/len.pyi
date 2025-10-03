from typing import Tuple, TypeVar, Generic, Union, Type, Sequence, Mapping
from typing_extensions import Protocol

T = TypeVar("T")
V = TypeVar("V")

class object:
    def __init__(self) -> None: pass

class type:
    def __init__(self, x) -> None: pass

class tuple(Sequence[T]):
    def __len__(self) -> int: pass

class list(Sequence[T]): pass
class dict(Mapping[T, V]): pass

class function: pass

class Sized(Protocol):
    def __len__(self) -> int: pass

def len(__obj: Sized) -> int: ...
def isinstance(x: object, t: Union[Type[object], Tuple[Type[object], ...]]) -> bool: pass

class int:
    def __add__(self, other: int) -> int: pass
    def __eq__(self, other: int) -> bool: pass
    def __ne__(self, other: int) -> bool: pass
    def __lt__(self, n: int) -> bool: pass
    def __gt__(self, n: int) -> bool: pass
    def __le__(self, n: int) -> bool: pass
    def __ge__(self, n: int) -> bool: pass
    def __neg__(self) -> int: pass
class float: pass
class bool(int): pass
class str(Sequence[str]): pass
class ellipsis: pass
