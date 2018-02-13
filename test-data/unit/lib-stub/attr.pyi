from typing import TypeVar, overload, Callable, Any, Type, Optional

_T = TypeVar('_T')
_C = TypeVar('_C', bound=type)

@overload
def attr(default: Optional[_T] = ...,
         validator: Optional[Any] = ...,
         repr: bool = ...,
         cmp: bool = ...,
         hash: Optional[bool] = ...,
         init: bool = ...,
         convert: Optional[Callable[[Any], _T]] = ...,
         metadata: Any = ...,
         type: Optional[Type[_T]] = ...,
         converter: Optional[Callable[[Any], _T]] = ...) -> _T: ...
@overload
def attr(default: None = ...,
         validator: None = ...,
         repr: bool = ...,
         cmp: bool = ...,
         hash: Optional[bool] = ...,
         init: bool = ...,
         convert: Optional[Callable[[Any], _T]] = ...,
         metadata: Any = ...,
         type: None = ...,
         converter: None = ...) -> Any: ...

@overload
def attributes(maybe_cls: _C,
               these: Optional[Any] = ...,
               repr_ns: Optional[str] = ...,
               repr: bool = ...,
               cmp: bool = ...,
               hash: Optional[bool] = ...,
               init: bool = ...,
               slots: bool = ...,
               frozen: bool = ...,
               str: bool = ...,
               auto_attribs: bool = ...) -> _C: ...
@overload
def attributes(maybe_cls: None = ...,
               these: Optional[Any] = ...,
               repr_ns: Optional[str] = ...,
               repr: bool = ...,
               cmp: bool = ...,
               hash: Optional[bool] = ...,
               init: bool = ...,
               slots: bool = ...,
               frozen: bool = ...,
               str: bool = ...,
               auto_attribs: bool = ...) -> Callable[[_C], _C]: ...

# aliases
s = attrs = attributes
ib = attrib = attr
dataclass = attrs # Technically, partial(attrs, auto_attribs=True) ;)
