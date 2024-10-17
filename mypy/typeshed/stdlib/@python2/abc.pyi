import _weakrefset
from _typeshed import SupportsWrite
from typing import Any, Callable, TypeVar

_FuncT = TypeVar("_FuncT", bound=Callable[..., Any])

# NOTE: mypy has special processing for ABCMeta and abstractmethod.

def abstractmethod(funcobj: _FuncT) -> _FuncT: ...

class ABCMeta(type):
    __abstractmethods__: frozenset[str]
    _abc_cache: _weakrefset.WeakSet[Any]
    _abc_invalidation_counter: int
    _abc_negative_cache: _weakrefset.WeakSet[Any]
    _abc_negative_cache_version: int
    _abc_registry: _weakrefset.WeakSet[Any]
    def __init__(self, name: str, bases: tuple[type, ...], namespace: dict[str, Any]) -> None: ...
    def __instancecheck__(cls: ABCMeta, instance: Any) -> Any: ...
    def __subclasscheck__(cls: ABCMeta, subclass: Any) -> Any: ...
    def _dump_registry(cls: ABCMeta, file: SupportsWrite[Any] | None = ...) -> None: ...
    def register(cls: ABCMeta, subclass: type[Any]) -> None: ...

# TODO: The real abc.abstractproperty inherits from "property".
class abstractproperty(object):
    def __new__(cls, func: Any) -> Any: ...
    __isabstractmethod__: bool
    doc: Any
    fdel: Any
    fget: Any
    fset: Any
