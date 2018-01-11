from typing import TypeVar, overload, Callable, Any, Type

_T = TypeVar('_T')

@overload
def attr(default: _T = ..., validator: Any = ..., type: type = ...) -> _T: ...
@overload
def attr(default: None = ..., validator: Any = ..., type: type = ...) -> Any: ...

@overload
def attributes(maybe_cls: _T = ..., cmp: bool = ..., init: bool = ..., frozen: bool = ...) -> _T: ...
@overload
def attributes(maybe_cls: None = ..., cmp: bool = ..., init: bool = ..., frozen: bool = ...) -> Callable[[_T], _T]: ...

# aliases
s = attrs = attributes
ib = attrib = attr
dataclass = attrs # Technically, partial(attrs, auto_attribs=True) ;)
