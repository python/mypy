# builtins stub used in boolean-related test cases.
from typing import Generic, TypeVar
T = TypeVar('T')

class object:
    def __init__(self) -> None: pass
    def __eq__(self, other: object) -> bool: pass
    def __ne__(self, other: object) -> bool: pass

class type: pass
class function: pass
class int: pass
class bool(int): pass
class float: pass
class str: pass
class ellipsis: pass
class list(Generic[T]): pass
class property: pass
class dict: pass

# region ArgumentInferContext
from typing import Mapping, Generic, Iterator, TypeVar
_Tuple_co = TypeVar('_Tuple_co', covariant=True)
class tuple(Generic[_Tuple_co]):
    def __iter__(self) -> Iterator[_Tuple_co]: pass
# endregion ArgumentInferContext
