import sys
import types
from collections.abc import Coroutine
from typing import Any
from typing_extensions import TypeGuard

if sys.version_info >= (3, 11):
    __all__ = ("iscoroutinefunction", "iscoroutine")
elif sys.version_info >= (3, 7):
    __all__ = ("coroutine", "iscoroutinefunction", "iscoroutine")
else:
    __all__ = ["coroutine", "iscoroutinefunction", "iscoroutine"]

if sys.version_info < (3, 11):
    from collections.abc import Callable
    from typing import TypeVar

    _F = TypeVar("_F", bound=Callable[..., Any])
    def coroutine(func: _F) -> _F: ...

def iscoroutinefunction(func: object) -> bool: ...

if sys.version_info >= (3, 8):
    def iscoroutine(obj: object) -> TypeGuard[Coroutine[Any, Any, Any]]: ...

else:
    def iscoroutine(obj: object) -> TypeGuard[types.GeneratorType[Any, Any, Any] | Coroutine[Any, Any, Any]]: ...
