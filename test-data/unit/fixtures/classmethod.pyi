import typing

_T = typing.TypeVar('_T')

class object:
    def __init__(self) -> None: pass

class type:
    def __init__(self, x) -> None: pass
    def mro(self) -> typing.Any: pass

class function: pass

# Dummy definitions.
class classmethod: pass
class staticmethod: pass

class int:
    @classmethod
    def from_bytes(cls, bytes: bytes, byteorder: str) -> int: pass

class float: pass
class str: pass
class bytes: pass
class bool: pass
class ellipsis: pass

class list: pass
class dict: pass

# region ArgumentInferContext
from typing import Mapping, Generic, Iterator, TypeVar
_Tuple_co = TypeVar('_Tuple_co', covariant=True)
class tuple(Generic[_Tuple_co]):
    def __iter__(self) -> Iterator[_Tuple_co]: pass
# endregion ArgumentInferContext
