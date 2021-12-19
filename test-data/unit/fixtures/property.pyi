from typing import Any, Callable, Generic, TypeVar, Sequence

_T = TypeVar('_T')

class object:
    def __init__(self) -> None: pass

class type:
    def __init__(self, x: Any) -> None: pass

class function: pass

class property(object):
    fget: Callable[[Any], Any] | None
    fset: Callable[[Any, Any], None] | None
    fdel: Callable[[Any], None] | None
    def __init__(
        self,
        fget: Callable[[Any], Any] | None = ...,
        fset: Callable[[Any, Any], None] | None = ...,
        fdel: Callable[[Any], None] | None = ...,
        doc: str | None = ...,
    ) -> None: ...
    def getter(self, __fget: Callable[[Any], Any]) -> property: ...
    def setter(self, __fset: Callable[[Any, Any], None]) -> property: ...
    def deleter(self, __fdel: Callable[[Any], None]) -> property: ...
    def __get__(self, __obj: Any, __type: type | None = ...) -> Any: ...
    def __set__(self, __obj: Any, __value: Any) -> None: ...
    def __delete__(self, __obj: Any) -> None: ...

class dict: pass
class int: pass
class str: pass
class float: pass
class bytes: pass
class bool: pass
class ellipsis: pass

class list(Sequence[_T]): pass
class tuple(Generic[_T]): pass
