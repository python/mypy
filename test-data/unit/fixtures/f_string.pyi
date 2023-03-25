# Builtins stub used for format-string-related test cases.
# We need str and list, and str needs join and format methods.

from typing import TypeVar, Generic, Iterable, Iterator, List, overload

T = TypeVar('T')

class object:
    def __init__(self): pass

class type:
    def __init__(self, x) -> None: pass

class ellipsis: pass

class list(Iterable[T], Generic[T]):
    @overload
    def __init__(self) -> None: pass
    @overload
    def __init__(self, x: Iterable[T]) -> None: pass
    def append(self, x: T) -> None: pass

class tuple(Generic[T]): pass

class function: pass
class int:
    def __add__(self, i: int) -> int: pass

class float: pass
class bool(int): pass

class str:
    def __add__(self, s: str) -> str: pass
    def format(self, *args) -> str: pass
    def join(self, l: List[str]) -> str: pass


class dict: pass
