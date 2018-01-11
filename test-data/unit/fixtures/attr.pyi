from typing import TypeVar, overload, Callable, Any

_T = TypeVar('_T')

@overload
def attr() -> Any: ...
@overload
def attr(default: _T, validator = ...) -> _T: ...
@overload
def attr(default: _T = ..., validator = ...) -> _T: ...
@overload
def attr(validator= ...) -> Any: ...

@overload
def attributes(maybe_cls: _T = ..., cmp: bool = ..., init: bool = ...) -> _T: ...

@overload
def attributes(maybe_cls: None = ..., cmp: bool = ..., init: bool = ...) -> Callable[[_T], _T]: ...

# aliases
s = attrs = attributes
ib = attrib = attr
