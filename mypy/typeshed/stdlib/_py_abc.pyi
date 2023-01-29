from _typeshed import Self
from typing import Any, NewType, TypeVar

_T = TypeVar("_T")

_CacheToken = NewType("_CacheToken", int)

def get_cache_token() -> _CacheToken: ...

class ABCMeta(type):
    def __new__(__mcls: type[Self], __name: str, __bases: tuple[type[Any], ...], __namespace: dict[str, Any]) -> Self: ...
    def register(cls, subclass: type[_T]) -> type[_T]: ...
