from typing import TypeVar, overload, Callable

_T = TypeVar('_T')

def attr(default: _T = ..., validator = ...) -> _T: ...

@overload
def attributes(maybe_cls: _T = ..., cmp: bool = ..., init: bool = ...) -> _T: ...

@overload
def attributes(maybe_cls: None = ..., cmp: bool = ..., init: bool = ...) -> Callable[[_T], _T]: ...

# aliases
s = attrs = attributes
ib = attrib = attr
