from typing import Generic, TypeVar
T = TypeVar('T')

Any = 0

class object:
    def __init__(self) -> None: pass

class type:
    def __init__(self, x: Any) -> None: pass

class str:
    def __add__(self, other: 'str') -> 'str': pass
    def __rmul__(self, n: int) -> str: ...

class bytes: pass

class tuple(Generic[T]): pass
class function: pass

class ellipsis: pass


class int:
    def __abs__(self) -> int: ...
    def __float__(self) -> float: ...
    def __int__(self) -> int: ...
    def __mul__(self, x: int) -> int: ...
    def __neg__(self) -> int: ...
    def __rmul__(self, x: int) -> int: ...

class float:
    def __float__(self) -> float: ...
    def __int__(self) -> int: ...
    def __mul__(self, x: float) -> float: ...
    def __rmul__(self, x: float) -> float: ...

class dict: pass
