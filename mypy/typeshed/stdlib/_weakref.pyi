import sys
from collections.abc import Callable
from typing import Any, Generic, TypeVar, overload
from typing_extensions import Self, final

if sys.version_info >= (3, 9):
    from types import GenericAlias

_C = TypeVar("_C", bound=Callable[..., Any])
_T = TypeVar("_T")

@final
class CallableProxyType(Generic[_C]):  # "weakcallableproxy"
    def __getattr__(self, attr: str) -> Any: ...
    __call__: _C

@final
class ProxyType(Generic[_T]):  # "weakproxy"
    def __getattr__(self, attr: str) -> Any: ...

class ReferenceType(Generic[_T]):
    __callback__: Callable[[ReferenceType[_T]], Any]
    def __new__(cls, o: _T, callback: Callable[[ReferenceType[_T]], Any] | None = ...) -> Self: ...
    def __call__(self) -> _T | None: ...
    if sys.version_info >= (3, 9):
        def __class_getitem__(cls, item: Any) -> GenericAlias: ...

ref = ReferenceType

def getweakrefcount(__object: Any) -> int: ...
def getweakrefs(__object: Any) -> list[Any]: ...

# Return CallableProxyType if object is callable, ProxyType otherwise
@overload
def proxy(__object: _C, __callback: Callable[[_C], Any] | None = None) -> CallableProxyType[_C]: ...
@overload
def proxy(__object: _T, __callback: Callable[[_T], Any] | None = None) -> Any: ...
