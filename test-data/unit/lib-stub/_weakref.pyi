from typing import Any, Callable, TypeVar, overload
from weakref import CallableProxyType, ProxyType

_C = TypeVar("_C", bound=Callable[..., Any])
_T = TypeVar("_T")

# Return CallableProxyType if object is callable, ProxyType otherwise
@overload
def proxy(object: _C, callback: Callable[[CallableProxyType[_C]], Any] | None = None, /) -> CallableProxyType[_C]: ...
@overload
def proxy(object: _T, callback: Callable[[ProxyType[_T]], Any] | None = None, /) -> ProxyType[_T]: ...
