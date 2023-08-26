from _typeshed import DataclassInstance
from typing import Any, Callable, Generic, Literal, Mapping, Optional, TypeVar, overload, Type
from typing_extensions import TypeGuard

_T = TypeVar('_T')
_DataclassT = TypeVar("_DataclassT", bound=DataclassInstance)

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
def is_dataclass(obj: DataclassInstance) -> Literal[True]: ...
@overload
def is_dataclass(obj: type) -> TypeGuard[type[DataclassInstance]]: ...
@overload
def is_dataclass(obj: object) -> TypeGuard[DataclassInstance | type[DataclassInstance]]: ...


def replace(__obj: _DataclassT, **changes: Any) -> _DataclassT: ...
