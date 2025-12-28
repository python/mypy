import typing

_T = typing.TypeVar('_T')

class object:
    def __init__(self) -> None: pass

class type:
    def __init__(self, x: typing.Any) -> None: pass

class function: pass

property = object()  # Dummy definition
class classmethod: pass

class list(typing.Generic[_T]): pass
class dict: pass
class int: pass
class float: pass
class str: pass
class bytes: pass
class bool: pass
class ellipsis: pass

# region ArgumentInferContext
from typing import Mapping, Generic, Iterator, TypeVar
_Tuple_co = TypeVar('_Tuple_co', covariant=True)
class tuple(Generic[_Tuple_co]):
    def __iter__(self) -> Iterator[_Tuple_co]: pass
# endregion ArgumentInferContext
