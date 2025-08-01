from collections.abc import Callable
from typing import Any, Generic, TypeVar
from typing_extensions import Self

_T = TypeVar("_T")

class ReferenceType(Generic[_T]):  # "weakref"
    __callback__: Callable[[Self], Any]
    def __new__(cls, o: _T, callback: Callable[[Self], Any] | None = ..., /) -> Self: ...

ref = ReferenceType
