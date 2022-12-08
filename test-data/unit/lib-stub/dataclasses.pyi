from typing import (
    Any, Callable, Generic, Mapping, Optional, TypeVar, overload, Tuple,
    Type,
)

_T = TypeVar('_T')

class InitVar(Generic[_T]):
    ...

class KW_ONLY: ...

@overload
def dataclass(_cls: Type[_T]) -> Type[_T]: ...

@overload
def dataclass(*, init: bool = ..., repr: bool = ..., eq: bool = ..., order: bool = ...,
    unsafe_hash: bool = ..., frozen: bool = ..., match_args: bool = ...,
    kw_only: bool = ..., slots: bool = ...) -> Callable[[Type[_T]], Type[_T]]: ...

@overload
def field(*, default: _T,
    init: bool = ..., repr: bool = ..., hash: Optional[bool] = ..., compare: bool = ...,
    metadata: Optional[Mapping[str, Any]] = ..., kw_only: bool = ...,) -> _T: ...

@overload
def field(*, default_factory: Callable[[], _T],
    init: bool = ..., repr: bool = ..., hash: Optional[bool] = ..., compare: bool = ...,
    metadata: Optional[Mapping[str, Any]] = ..., kw_only: bool = ...,) -> _T: ...

@overload
def field(*,
    init: bool = ..., repr: bool = ..., hash: Optional[bool] = ..., compare: bool = ...,
    metadata: Optional[Mapping[str, Any]] = ..., kw_only: bool = ...,) -> Any: ...


class Field(Generic[_T]): pass

@overload
def asdict(obj: Any) -> dict[str, Any]: ...

@overload
def asdict(obj: Any, *, dict_factory: Callable[[list[tuple[str, Any]]], _T]) -> _T: ...

@overload
def astuple(obj: Any) -> Tuple[Any, ...]: ...

@overload
def astuple(obj: Any, *, tuple_factory: Callable[[list[Any]], _T]) -> _T: ...

def replace(obj: _T, **changes: Any) -> _T: ...

def fields(class_or_instance: Any) -> Tuple[Field[Any], ...]: ...
