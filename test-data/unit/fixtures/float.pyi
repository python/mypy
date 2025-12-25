from typing import TypeVar, Any
T = TypeVar('T')

class object:
    def __init__(self) -> None: pass

class type:
    def __init__(self, x: Any) -> None: pass

class str:
    def __add__(self, other: 'str') -> 'str': pass
    def __rmul__(self, n: int) -> str: ...

class bytes: pass
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

# region ArgumentInferContext
from typing import Mapping, Generic, Iterator, TypeVar
_Tuple_co = TypeVar('_Tuple_co', covariant=True)
class tuple(Generic[_Tuple_co]):
    def __iter__(self) -> Iterator[_Tuple_co]: pass
# endregion ArgumentInferContext
