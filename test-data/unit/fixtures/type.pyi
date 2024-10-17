# builtins stub used in type-related test cases.

from typing import Any, Generic, TypeVar, List, Union
import sys
import types

T = TypeVar("T")
S = TypeVar("S")

class object:
    def __init__(self) -> None: pass
    def __str__(self) -> 'str': pass

class list(Generic[T]): pass

class type:
    __name__: str
    def __call__(self, *args: Any, **kwargs: Any) -> Any: pass
    def __or__(self, other: Union[type, None]) -> type: pass
    def __ror__(self, other: Union[type, None]) -> type: pass
    def mro(self) -> List['type']: pass

class tuple(Generic[T]): pass
class dict(Generic[T, S]): pass
class function: pass
class bool: pass
class int: pass
class str: pass
class ellipsis: pass
class float: pass

if sys.version_info >= (3, 10):  # type: ignore
    def isinstance(obj: object, class_or_tuple: type | types.UnionType, /) -> bool: ...
else:
    def isinstance(obj: object, class_or_tuple: type, /) -> bool: ...
