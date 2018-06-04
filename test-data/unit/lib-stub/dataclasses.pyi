from typing import Any, Callable, Generic, Mapping, Optional, TypeVar, overload

_T = TypeVar('_T')
_C = TypeVar('_C', bound=type)

class InitVar(Generic[_T]):
    ...


@overload
def dataclass(_cls: _C,
              *,
              init: bool = ...,
              repr: bool = ...,
              eq: bool = ...,
              order: bool = ...,
              unsafe_hash: bool = ...,
              frozen: bool = ...) -> _C: ...


@overload
def dataclass(_cls: None = ...,
              *,
              init: bool = ...,
              repr: bool = ...,
              eq: bool = ...,
              order: bool = ...,
              unsafe_hash: bool = ...,
              frozen: bool = ...) -> Callable[[_C], _C]: ...


@overload
def field(*, default: _T,
    init: bool = ..., repr: bool = ..., hash: Optional[bool] = ..., compare: bool = ...,
    metadata: Optional[Mapping[str, Any]] = ...) -> _T: ...

@overload
def field(*, default_factory: Callable[[], _T],
    init: bool = ..., repr: bool = ..., hash: Optional[bool] = ..., compare: bool = ...,
    metadata: Optional[Mapping[str, Any]] = ...) -> _T: ...

@overload
def field(*,
    init: bool = ..., repr: bool = ..., hash: Optional[bool] = ..., compare: bool = ...,
    metadata: Optional[Mapping[str, Any]] = ...) -> Any: ...