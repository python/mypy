from typing import TypeVar, overload, Callable, Any, Optional, Union, Sequence, Mapping, \
    Protocol, ClassVar, Type
from typing_extensions import TypeGuard

from attr import Attribute as Attribute


class AttrsInstance(Protocol):
    __attrs_attrs__: ClassVar[Any]


_T = TypeVar('_T')
_C = TypeVar('_C', bound=type)

_ValidatorType = Callable[[Any, Any, _T], Any]
_ConverterType = Callable[[Any], _T]
_ValidatorArgType = Union[_ValidatorType[_T], Sequence[_ValidatorType[_T]]]

@overload
def define(
    maybe_cls: _C,
    *,
    these: Optional[Mapping[str, Any]] = ...,
    repr: bool = ...,
    unsafe_hash: Optional[bool]=None,
    hash: Optional[bool] = ...,
    init: bool = ...,
    slots: bool = ...,
    frozen: bool = ...,
    weakref_slot: bool = ...,
    str: bool = ...,
    auto_attribs: bool = ...,
    kw_only: bool = ...,
    cache_hash: bool = ...,
    auto_exc: bool = ...,
    eq: Optional[bool] = ...,
    order: Optional[bool] = ...,
    auto_detect: bool = ...,
    getstate_setstate: Optional[bool] = ...,
    on_setattr: Optional[object] = ...,
) -> _C: ...
@overload
def define(
    maybe_cls: None = ...,
    *,
    these: Optional[Mapping[str, Any]] = ...,
    repr: bool = ...,
    unsafe_hash: Optional[bool]=None,
    hash: Optional[bool] = ...,
    init: bool = ...,
    slots: bool = ...,
    frozen: bool = ...,
    weakref_slot: bool = ...,
    str: bool = ...,
    auto_attribs: bool = ...,
    kw_only: bool = ...,
    cache_hash: bool = ...,
    auto_exc: bool = ...,
    eq: Optional[bool] = ...,
    order: Optional[bool] = ...,
    auto_detect: bool = ...,
    getstate_setstate: Optional[bool] = ...,
    on_setattr: Optional[object] = ...,
) -> Callable[[_C], _C]: ...

mutable = define
frozen = define  # they differ only in their defaults

@overload
def field(
    *,
    default: None = ...,
    validator: None = ...,
    repr: object = ...,
    hash: Optional[bool] = ...,
    init: bool = ...,
    metadata: Optional[Mapping[Any, Any]] = ...,
    converter: None = ...,
    factory: None = ...,
    kw_only: bool = ...,
    eq: Optional[bool] = ...,
    order: Optional[bool] = ...,
    on_setattr: Optional[_OnSetAttrArgType] = ...,
    alias: Optional[str] = ...,
) -> Any: ...

# This form catches an explicit None or no default and infers the type from the
# other arguments.
@overload
def field(
    *,
    default: None = ...,
    validator: Optional[_ValidatorArgType[_T]] = ...,
    repr: object = ...,
    hash: Optional[bool] = ...,
    init: bool = ...,
    metadata: Optional[Mapping[Any, Any]] = ...,
    converter: Optional[_ConverterType] = ...,
    factory: Optional[Callable[[], _T]] = ...,
    kw_only: bool = ...,
    eq: Optional[bool] = ...,
    order: Optional[bool] = ...,
    on_setattr: Optional[object] = ...,
    alias: Optional[str] = ...,
) -> _T: ...

# This form catches an explicit default argument.
@overload
def field(
    *,
    default: _T,
    validator: Optional[_ValidatorArgType[_T]] = ...,
    repr: object = ...,
    hash: Optional[bool] = ...,
    init: bool = ...,
    metadata: Optional[Mapping[Any, Any]] = ...,
    converter: Optional[_ConverterType] = ...,
    factory: Optional[Callable[[], _T]] = ...,
    kw_only: bool = ...,
    eq: Optional[bool] = ...,
    order: Optional[bool] = ...,
    on_setattr: Optional[object] = ...,
    alias: Optional[str] = ...,
) -> _T: ...

# This form covers type=non-Type: e.g. forward references (str), Any
@overload
def field(
    *,
    default: Optional[_T] = ...,
    validator: Optional[_ValidatorArgType[_T]] = ...,
    repr: object = ...,
    hash: Optional[bool] = ...,
    init: bool = ...,
    metadata: Optional[Mapping[Any, Any]] = ...,
    converter: Optional[_ConverterType] = ...,
    factory: Optional[Callable[[], _T]] = ...,
    kw_only: bool = ...,
    eq: Optional[bool] = ...,
    order: Optional[bool] = ...,
    on_setattr: Optional[object] = ...,
    alias: Optional[str] = ...,
) -> Any: ...

def evolve(inst: _T, **changes: Any) -> _T: ...
def assoc(inst: _T, **changes: Any) -> _T: ...
def has(cls: type) -> TypeGuard[Type[AttrsInstance]]: ...
def fields(cls: Type[AttrsInstance]) -> Any: ...
