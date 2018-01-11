from typing import TypeVar, overload, Callable, Any, Type, Optional

_T = TypeVar('_T')

@overload
def attr(default: _T = ..., validator: Any = ..., init: bool = ..., convert: Optional[Callable[[Any], _T]] = ..., type: Optional[Callable[..., _T]] = ..., converter: Optional[Callable[[Any], _T]] = ...) -> _T: ...
@overload
def attr(default: None = ..., validator: None = ..., init: bool = ..., convert: None = ..., type: None = ..., converter: Optional[Callable[[Any], _T]] = ...) -> Any: ...

@overload
def attributes(maybe_cls: _T = ..., cmp: bool = ..., init: bool = ..., frozen: bool = ...) -> _T: ...
@overload
def attributes(maybe_cls: None = ..., cmp: bool = ..., init: bool = ..., frozen: bool = ...) -> Callable[[_T], _T]: ...

# aliases
s = attrs = attributes
ib = attrib = attr
dataclass = attrs # Technically, partial(attrs, auto_attribs=True) ;)
