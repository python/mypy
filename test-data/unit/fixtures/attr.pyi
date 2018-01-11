from typing import TypeVar, overload, Callable, Any

_T = TypeVar('_T')

def attr(default: Any = ..., validator: Any = ...) -> Any: ...

@overload
def attributes(maybe_cls: _T = ..., cmp: bool = ..., init: bool = ...) -> _T: ...
@overload
def attributes(maybe_cls: None = ..., cmp: bool = ..., init: bool = ...) -> Callable[[_T], _T]: ...

# aliases
s = attrs = attributes
ib = attrib = attr
