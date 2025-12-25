from typing import Any, Dict, Generic, TypeVar, Sequence
from types import ModuleType

T = TypeVar('T')
S = TypeVar('S')

class list(Generic[T], Sequence[T]): pass  # type: ignore

class object:
    def __init__(self) -> None: pass
class type: pass
class function: pass
class int: pass
class float: pass
class str: pass
class bool: pass
class dict(Generic[T, S]): pass
class ellipsis: pass

classmethod = object()
staticmethod = object()
property = object()
def hasattr(x: object, name: str) -> bool: pass

# region ArgumentInferContext
from typing import Mapping, Generic, Iterator, TypeVar
_Tuple_co = TypeVar('_Tuple_co', covariant=True)
class tuple(Generic[_Tuple_co]):
    def __iter__(self) -> Iterator[_Tuple_co]: pass
# endregion ArgumentInferContext
