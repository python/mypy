import sys
from _typeshed import SupportsWrite
from collections.abc import Callable
from typing import Any, Generic, TypeVar
from typing_extensions import Literal

_T = TypeVar("_T")
_R_co = TypeVar("_R_co", covariant=True)
_FuncT = TypeVar("_FuncT", bound=Callable[..., Any])

# These definitions have special processing in mypy
class ABCMeta(type):
    __abstractmethods__: frozenset[str]
    def __init__(self, name: str, bases: tuple[type, ...], namespace: dict[str, Any]) -> None: ...
    def __instancecheck__(cls: ABCMeta, instance: Any) -> Any: ...
    def __subclasscheck__(cls: ABCMeta, subclass: Any) -> Any: ...
    def _dump_registry(cls: ABCMeta, file: SupportsWrite[str] | None = ...) -> None: ...
    def register(cls: ABCMeta, subclass: type[_T]) -> type[_T]: ...

def abstractmethod(funcobj: _FuncT) -> _FuncT: ...

class abstractclassmethod(classmethod[_R_co], Generic[_R_co]):
    __isabstractmethod__: Literal[True]
    def __init__(self: abstractclassmethod[_R_co], callable: Callable[..., _R_co]) -> None: ...

class abstractstaticmethod(staticmethod[_R_co], Generic[_R_co]):
    __isabstractmethod__: Literal[True]
    def __init__(self, callable: Callable[..., _R_co]) -> None: ...

class abstractproperty(property):
    __isabstractmethod__: Literal[True]

class ABC(metaclass=ABCMeta): ...

def get_cache_token() -> object: ...

if sys.version_info >= (3, 10):
    def update_abstractmethods(cls: type[_T]) -> type[_T]: ...
