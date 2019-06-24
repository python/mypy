# builtins stub with non-generic primitive types
from typing import Generic, TypeVar, Sequence, Iterator
T = TypeVar('T')

class object:
    def __init__(self) -> None: pass
    def __str__(self) -> str: pass
    def __eq__(self, other: object) -> bool: pass
    def __ne__(self, other: object) -> bool: pass

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
