from typing import TypeVar, Tuple, SupportsInt
class object:
    def __init__(self): pass

class int(SupportsInt):
    def __divmod__(self, other: int) -> Tuple[int, int]: pass
    def __rdivmod__(self, other: int) -> Tuple[int, int]: pass

class float(SupportsInt):
    def __divmod__(self, other: float) -> Tuple[float, float]: pass
    def __rdivmod__(self, other: float) -> Tuple[float, float]: pass


class function: pass
class str: pass
class type: pass
class ellipsis: pass

_N = TypeVar('_N', int, float)
def divmod(_x: _N, _y: _N) -> Tuple[_N, _N]: ...

class dict: pass

# region ArgumentInferContext
from typing import Mapping, Generic, Iterator, TypeVar
_Tuple_co = TypeVar('_Tuple_co', covariant=True)
class tuple(Generic[_Tuple_co]):
    def __iter__(self) -> Iterator[_Tuple_co]: pass
# endregion ArgumentInferContext
