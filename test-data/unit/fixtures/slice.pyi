# Builtins stub used in slicing test cases.
from typing import Generic, TypeVar
T = TypeVar('T')

class object:
    def __init__(self): pass

class type: pass
class function: pass

class int: pass
class str: pass

class slice: pass
class ellipsis: pass
class dict: pass
class list(Generic[T]):
    def __getitem__(self, x: slice) -> list[T]: pass

# region ArgumentInferContext
from typing import Mapping, Generic, Iterator, TypeVar
_Tuple_co = TypeVar('_Tuple_co', covariant=True)
class tuple(Generic[_Tuple_co]):
    def __iter__(self) -> Iterator[_Tuple_co]: pass
# endregion ArgumentInferContext
