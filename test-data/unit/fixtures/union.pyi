# Builtins stub used in tuple-related test cases.

from isinstance import isinstance
from typing import Iterable, TypeVar, Generic
T = TypeVar('T')

class object:
    def __init__(self): pass

class type: pass
class function: pass

# We need int for indexing tuples.
class int: pass
class str: pass # For convenience
class dict: pass

# region ArgumentInferContext
from typing import Mapping, Generic, Iterator, TypeVar
_Tuple_co = TypeVar('_Tuple_co', covariant=True)
class tuple(Generic[_Tuple_co]):
    def __iter__(self) -> Iterator[_Tuple_co]: pass
# endregion ArgumentInferContext
