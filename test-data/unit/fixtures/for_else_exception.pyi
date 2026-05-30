# Fixture for for-else tests with exceptions
# Combines needed elements from primitives.pyi and exception.pyi

from typing import Generic, Iterator, Mapping, Sequence, TypeVar

T = TypeVar('T')
V = TypeVar('V')

class object:
    def __init__(self) -> None: pass
class type:
    def __init__(self, x: object) -> None: pass
class int:
    def __init__(self, x: object = ..., base: int = ...) -> None: pass
    def __add__(self, i: int) -> int: pass
    def __rmul__(self, x: int) -> int: pass
    def __bool__(self) -> bool: pass
    def __eq__(self, x: object) -> bool: pass
    def __ne__(self, x: object) -> bool: pass
    def __lt__(self, x: 'int') -> bool: pass
    def __le__(self, x: 'int') -> bool: pass
    def __gt__(self, x: 'int') -> bool: pass
    def __ge__(self, x: 'int') -> bool: pass
class float:
    def __float__(self) -> float: pass
    def __add__(self, x: float) -> float: pass
    def hex(self) -> str: pass
class bool(int): pass
class str(Sequence[str]):
    def __add__(self, s: str) -> str: pass
    def __iter__(self) -> Iterator[str]: pass
    def __contains__(self, other: object) -> bool: pass
    def __getitem__(self, item: int) -> str: pass
    def format(self, *args: object, **kwargs: object) -> str: pass
class dict(Mapping[T, V]):
    def __iter__(self) -> Iterator[T]: pass
class tuple(Generic[T]):
    def __contains__(self, other: object) -> bool: pass
class ellipsis: pass

class BaseException:
    def __init__(self, *args: object) -> None: ...
class Exception(BaseException): pass
class RuntimeError(Exception): pass

class range(Sequence[int]):
    def __init__(self, __x: int, __y: int = ..., __z: int = ...) -> None: pass
    def count(self, value: int) -> int: pass
    def index(self, value: int) -> int: pass
    def __getitem__(self, i: int) -> int: pass
    def __iter__(self) -> Iterator[int]: pass
    def __contains__(self, other: object) -> bool: pass

def print(x: object) -> None: pass
