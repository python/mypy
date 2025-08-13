import typing

T = typing.TypeVar('T')
U = typing.TypeVar('U')
class list(typing.Sequence[T]):
    def __iter__(self) -> typing.Iterator[T]: ...
    def __getitem__(self, i: int) -> T: ...
    def __contains__(self, item: object) -> bool: ...

class object:
    def __init__(self) -> None: pass
class type: pass
class function: pass
class int: pass
class float: pass
class str: pass
class bool(int): pass
class dict(typing.Generic[T, U]): pass
class set(typing.Generic[T]): pass
class BaseException: pass
class StopIteration(BaseException): pass
class StopAsyncIteration(BaseException): pass
def iter(obj: typing.Any) -> typing.Any: pass
def next(obj: typing.Any) -> typing.Any: pass
class ellipsis: ...

# region ArgumentInferContext
from typing import Mapping, Generic, Iterator, TypeVar
_Tuple_co = TypeVar('_Tuple_co', covariant=True)
class tuple(Generic[_Tuple_co]):
    def __iter__(self) -> Iterator[_Tuple_co]: pass
# endregion ArgumentInferContext
