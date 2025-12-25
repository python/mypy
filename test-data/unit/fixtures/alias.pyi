# Builtins test fixture with a type alias 'bytes'

class object:
    def __init__(self) -> None: pass
class type:
    def __init__(self, x) -> None: pass

class int: pass
class str: pass
class function: pass

bytes = str

class dict: pass

# region ArgumentInferContext
from typing import Mapping, Generic, Iterator, TypeVar
_Tuple_co = TypeVar('_Tuple_co', covariant=True)
class tuple(Generic[_Tuple_co]):
    def __iter__(self) -> Iterator[_Tuple_co]: pass
# endregion ArgumentInferContext
