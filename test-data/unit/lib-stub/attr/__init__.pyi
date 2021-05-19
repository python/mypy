from typing import Tuple, TypeVar, overload, Callable, Any, Type, Optional, Union, Sequence, Mapping, Generic, List, Dict

_T = TypeVar('_T')
_C = TypeVar('_C', bound=type)

_ValidatorType = Callable[[Any, Any, _T], Any]
_ConverterType = Callable[[Any], _T]
_FilterType = Callable[[Any, Any], bool]
_ValidatorArgType = Union[_ValidatorType[_T], Sequence[_ValidatorType[_T]]]

_EqOrderType = Union[bool, Callable[[Any], Any]]
_ReprType = Callable[[Any], str]
_ReprArgType = Union[bool, _ReprType]
_OnSetAttrType = Callable[[Any, Attribute[Any], Any], Any]
_OnSetAttrArgType = Union[
    _OnSetAttrType, List[_OnSetAttrType]
]
_FieldTransformer = Callable[[type, List[Attribute[Any]]], List[Attribute[Any]]]

# This form catches explicit None or no default but with no other arguments returns Any.
@overload
def attrib(default: None = ...,
           validator: None = ...,
           repr: bool = ...,
           cmp: Optional[bool] = ...,
           hash: Optional[bool] = ...,
           init: bool = ...,
           convert: None = ...,
           metadata: Optional[Mapping[Any, Any]] = ...,
           type: None = ...,
           converter: None = ...,
           factory: None = ...,
           kw_only: bool = ...,
           eq: Optional[bool] = ...,
           order: Optional[bool] = ...,
           ) -> Any: ...
# This form catches an explicit None or no default and infers the type from the other arguments.
@overload
def attrib(default: None = ...,
           validator: Optional[_ValidatorArgType[_T]] = ...,
           repr: bool = ...,
           cmp: Optional[bool] = ...,
           hash: Optional[bool] = ...,
           init: bool = ...,
           convert: Optional[_ConverterType[_T]] = ...,
           metadata: Optional[Mapping[Any, Any]] = ...,
           type: Optional[Type[_T]] = ...,
           converter: Optional[_ConverterType[_T]] = ...,
           factory: Optional[Callable[[], _T]] = ...,
           kw_only: bool = ...,
           eq: Optional[bool] = ...,
           order: Optional[bool] = ...,
           ) -> _T: ...
# This form catches an explicit default argument.
@overload
def attrib(default: _T,
           validator: Optional[_ValidatorArgType[_T]] = ...,
           repr: bool = ...,
           cmp: Optional[bool] = ...,
           hash: Optional[bool] = ...,
           init: bool = ...,
           convert: Optional[_ConverterType[_T]] = ...,
           metadata: Optional[Mapping[Any, Any]] = ...,
           type: Optional[Type[_T]] = ...,
           converter: Optional[_ConverterType[_T]] = ...,
           factory: Optional[Callable[[], _T]] = ...,
           kw_only: bool = ...,
           eq: Optional[bool] = ...,
           order: Optional[bool] = ...,
           ) -> _T: ...
# This form covers type=non-Type: e.g. forward references (str), Any
@overload
def attrib(default: Optional[_T] = ...,
           validator: Optional[_ValidatorArgType[_T]] = ...,
           repr: bool = ...,
           cmp: Optional[bool] = ...,
           hash: Optional[bool] = ...,
           init: bool = ...,
           convert: Optional[_ConverterType[_T]] = ...,
           metadata: Optional[Mapping[Any, Any]] = ...,
           type: object = ...,
           converter: Optional[_ConverterType[_T]] = ...,
           factory: Optional[Callable[[], _T]] = ...,
           kw_only: bool = ...,
           eq: Optional[bool] = ...,
           order: Optional[bool] = ...,
           ) -> Any: ...

@overload
def attrs(maybe_cls: _C,
          these: Optional[Mapping[str, Any]] = ...,
          repr_ns: Optional[str] = ...,
          repr: bool = ...,
          cmp: Optional[bool] = ...,
          hash: Optional[bool] = ...,
          init: bool = ...,
          slots: bool = ...,
          frozen: bool = ...,
          weakref_slot: bool = ...,
          str: bool = ...,
          auto_attribs: bool = ...,
          kw_only: bool = ...,
          cache_hash: bool = ...,
          eq: Optional[bool] = ...,
          order: Optional[bool] = ...,
          ) -> _C: ...
@overload
def attrs(maybe_cls: None = ...,
          these: Optional[Mapping[str, Any]] = ...,
          repr_ns: Optional[str] = ...,
          repr: bool = ...,
          cmp: Optional[bool] = ...,
          hash: Optional[bool] = ...,
          init: bool = ...,
          slots: bool = ...,
          frozen: bool = ...,
          weakref_slot: bool = ...,
          str: bool = ...,
          auto_attribs: bool = ...,
          kw_only: bool = ...,
          cache_hash: bool = ...,
          eq: Optional[bool] = ...,
          order: Optional[bool] = ...,
          ) -> Callable[[_C], _C]: ...


# aliases
s = attributes = attrs
ib = attr = attrib
dataclass = attrs # Technically, partial(attrs, auto_attribs=True) ;)

# Next Generation API
@overload
def define(
    maybe_cls: _C,
    *,
    these: Optional[Mapping[str, Any]] = ...,
    repr: bool = ...,
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
) -> Any: ...


class Attribute(Generic[_T]):
    name: str
    default: Optional[_T]
    validator: Optional[_ValidatorType[_T]]
    repr: _ReprArgType
    cmp: _EqOrderType
    eq: _EqOrderType
    order: _EqOrderType
    hash: Optional[bool]
    init: bool
    converter: Optional[_ConverterType]
    metadata: Dict[Any, Any]
    type: Optional[Type[_T]]
    kw_only: bool
    on_setattr: _OnSetAttrType

    def evolve(self, **changes: Any) -> "Attribute[Any]": ...


class _Fields(Tuple[Attribute[Any], ...]):
    def __getattr__(self, name: str) -> Attribute[Any]: ...


def fields(cls: type) -> _Fields: ...
