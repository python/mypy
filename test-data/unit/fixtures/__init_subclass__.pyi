# builtins stub with object.__init_subclass__

class object:
    def __init_subclass__(cls) -> None: pass

class type: pass

class int: pass
class bool: pass
class str: pass
class function: pass
class dict: pass

# region ArgumentInferContext
from typing import Mapping, Generic, Iterator, TypeVar
_Tuple_co = TypeVar('_Tuple_co', covariant=True)
class tuple(Generic[_Tuple_co]):
    def __iter__(self) -> Iterator[_Tuple_co]: pass
# endregion ArgumentInferContext
