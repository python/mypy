from typing import TypeVar
_T = TypeVar('_T')

class object:
    def __init__(self): pass

class type: pass
class function: pass
class int: pass
class float: pass
class complex: pass
class str: pass
class ellipsis: pass
class dict: pass

# region ArgumentInferContext
from typing import Mapping, Generic, Iterator, TypeVar
_Tuple_co = TypeVar('_Tuple_co', covariant=True)
class tuple(Generic[_Tuple_co]):
    def __iter__(self) -> Iterator[_Tuple_co]: pass
# endregion ArgumentInferContext
