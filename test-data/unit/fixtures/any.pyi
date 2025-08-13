from typing import TypeVar, Iterable

T = TypeVar('T')

class int: pass
class str: pass

def any(i: Iterable[T]) -> bool: pass

class dict: pass

# region ArgumentInferContext
from typing import Mapping, Generic, Iterator, TypeVar
_Tuple_co = TypeVar('_Tuple_co', covariant=True)
class tuple(Generic[_Tuple_co]):
    def __iter__(self) -> Iterator[_Tuple_co]: pass
# endregion ArgumentInferContext
