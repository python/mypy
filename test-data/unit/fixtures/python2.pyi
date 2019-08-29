from typing import Generic, Iterable, TypeVar

class object:
    def __init__(self) -> None: pass
    def __eq__(self, other: object) -> bool: pass
    def __ne__(self, other: object) -> bool: pass

class type:
    def __init__(self, x) -> None: pass

class function: pass

class int: pass
class str:
    def format(self, *args, **kwars) -> str: ...
class unicode:
    def format(self, *args, **kwars) -> unicode: ...
class bool: pass

T = TypeVar('T')
S = TypeVar('S')
class list(Iterable[T], Generic[T]): pass
class tuple(Iterable[T]): pass
class dict(Generic[T, S]): pass

# Definition of None is implicit
