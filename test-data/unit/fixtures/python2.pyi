from typing import Generic, Iterable, TypeVar, Sequence, Iterator

class object:
    def __init__(self) -> None: pass
    def __eq__(self, other: object) -> bool: pass
    def __ne__(self, other: object) -> bool: pass

class type:
    def __init__(self, x) -> None: pass

class function: pass

class int: pass
class str: pass
class unicode: pass
class bool(int): pass
class bytearray(Sequence[int]):
    def __init__(self, string: str) -> None: pass
    def __contains__(self, item: object) -> bool: pass
    def __iter__(self) -> Iterator[int]: pass
    def __getitem__(self, item: int) -> int: pass

T = TypeVar('T')
class list(Iterable[T], Generic[T]):
    def __iter__(self) -> Iterator[T]: pass
    def __getitem__(self, item: int) -> T: pass

# Definition of None is implicit
