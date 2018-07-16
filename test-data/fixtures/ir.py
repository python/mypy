# These builtins stubs are used implicitly in AST to IR generation
# test cases.

from typing import (
    TypeVar, Generic, List, Iterator, Iterable, Sized, Dict, Optional, Tuple, Any,
    overload,
)

T = TypeVar('T')
S = TypeVar('S')

class object:
    def __init__(self) -> None: pass
    def __eq__(self, x: object) -> bool: pass
    def __ne__(self, x: object) -> bool: pass

class type:
    def __init__(self, o: object) -> None: ...

class ellipsis: pass

# Primitive types are special in generated code.

class int:
    def __init__(self, x: object) -> None: pass
    def __add__(self, n: int) -> int: pass
    def __sub__(self, n: int) -> int: pass
    def __mul__(self, n: int) -> int: pass
    def __floordiv__(self, x: int) -> int: pass
    def __mod__(self, x: int) -> int: pass
    def __neg__(self) -> int: pass
    def __pos__(self) -> int: pass
    def __eq__(self, n: object) -> bool: pass
    def __ne__(self, n: object) -> bool: pass
    def __lt__(self, n: int) -> bool: pass
    def __gt__(self, n: int) -> bool: pass
    def __le__(self, n: int) -> bool: pass
    def __ge__(self, n: int) -> bool: pass

class str:
    def __init__(self, x: object) -> None: pass
    def __add__(self, x: str) -> str: pass
    def __eq__(self, x: object) -> bool: pass
    def __ne__(self, x: object) -> bool: pass
    def join(self, x: Iterable[str]) -> str: pass

class float:
    def __init__(self, x: object) -> None: pass
    def __add__(self, n: float) -> float: pass
    def __sub__(self, n: float) -> float: pass
    def __mul__(self, n: float) -> float: pass
    def __div__(self, n: float) -> float: pass

class bool: pass

class tuple(Generic[T], Sized):
    def __init__(self, i: Iterable[T]) -> None: pass
    def __getitem__(self, i: int) -> T: pass
    def __len__(self) -> int: pass

class function: pass

class list(Generic[T], Iterable[T], Sized):
    def __getitem__(self, i: int) -> T: pass
    def __setitem__(self, i: int, o: T) -> None: pass
    def __mul__(self, i: int) -> List[T]: pass
    def __rmul__(self, i: int) -> List[T]: pass
    def __iter__(self) -> Iterator[T]: pass
    def __len__(self) -> int: pass
    def append(self, x: T) -> None: pass
    def pop(self) -> T: pass
    def extend(self, l: Iterable[T]) -> None: pass

class dict(Generic[T, S]):
    def __getitem__(self, x: T) -> S: pass
    def __setitem__(self, x: T, y: S) -> None: pass
    def __contains__(self, x: T) -> bool: pass
    def __iter__(self) -> Iterator[T]: pass
    def update(self, x: Dict[T, S]) -> None: pass
    def pop(self, x: int) -> T: pass

class slice: pass

class BaseException: pass

class Exception(BaseException):
    def __init__(self, message: Optional[str] = None) -> None: pass

class AttributeError(Exception): pass

class LookupError(Exception): pass

class KeyError(LookupError): pass

class IndexError(LookupError): pass


def id(o: object) -> int: pass
def len(o: Sized) -> int: pass
def print(*object) -> None: pass
def range(x: int) -> Iterator[int]: pass
def isinstance(x: object, t: object) -> bool: pass
