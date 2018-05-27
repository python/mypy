from typing import Any, Callable, Generic, Optional, TypeVar, overload

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


def field(*,
          default: Optional[_T] = ...,
          default_factory: Optional[Callable[..., _T]] = ...,
          init: bool = ...,
          repr: bool = ...,
          hash: Optional[bool] = ...,
          compare: bool = ...,
          metadata: Any = ...) -> _T: ...
