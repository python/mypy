from typing import Any, Callable, Dict, Generic, Iterable, List, Optional, \
    Mapping, Tuple, Type, TypeVar, Union, overload, Sequence

# `import X as X` is required to expose these to mypy. otherwise they are invisible
#from . import exceptions as exceptions
#from . import filters as filters
#from . import converters as converters
#from . import validators as validators

# typing --

_T = TypeVar('_T')
_C = TypeVar('_C', bound=type)
_M = TypeVar('_M', bound=Mapping)
_I = TypeVar('_I', bound=Sequence)

_ValidatorType = Callable[[Any, 'Attribute', _T], Any]
_ConverterType = Callable[[Any], _T]
_FilterType = Callable[['Attribute', Any], bool]

# _make --

NOTHING : object

# Factory lies about its return type to make this possible: `x: List[int] = Factory(list)`
def Factory(factory: Union[Callable[[], _T], Callable[[Any], _T]], takes_self: bool = ...) -> _T: ...

class Attribute(Generic[_T]):
    __slots__ = ("name", "default", "validator", "repr", "cmp", "hash", "init", "convert", "metadata", "type")
    name: str
    default: Any
    validator: Optional[Union[_ValidatorType[_T], List[_ValidatorType[_T]], Tuple[_ValidatorType[_T], ...]]]
    repr: bool
    cmp: bool
    hash: Optional[bool]
    init: bool
    convert: Optional[_ConverterType[_T]]
    metadata: Mapping
    type: Optional[Type[_T]]

@overload
def attr(default: _T = ..., validator: Optional[Union[_ValidatorType[_T], List[_ValidatorType[_T]], Tuple[_ValidatorType[_T], ...]]] = ..., repr: bool = ..., cmp: bool = ..., hash: Optional[bool] = ..., init: bool = ..., convert: Optional[_ConverterType[_T]] = ..., metadata: Mapping = ..., type: Any = ...) -> _T: ...
@overload
def attr(*, validator: Optional[Union[_ValidatorType[Any], List[_ValidatorType[Any]], Tuple[_ValidatorType[_T], ...]]] = ..., repr: bool = ..., cmp: bool = ..., hash: Optional[bool] = ..., init: bool = ..., convert: Optional[_ConverterType[Any]] = ..., metadata: Mapping = ...): ...


@overload
def attributes(maybe_cls: _C = ..., these: Optional[Dict[str, Any]] = ..., repr_ns: Optional[str] = ..., repr: bool = ..., cmp: bool = ..., hash: Optional[bool] = ..., init: bool = ..., slots: bool = ..., frozen: bool = ..., str: bool = ...) -> _C: ...
@overload
def attributes(maybe_cls: None = ..., these: Optional[Dict[str, Any]] = ..., repr_ns: Optional[str] = ..., repr: bool = ..., cmp: bool = ..., hash: Optional[bool] = ..., init: bool = ..., slots: bool = ..., frozen: bool = ..., str: bool = ...) -> Callable[[_C], _C]: ...

def fields(cls: type) -> Tuple[Attribute, ...]: ...
def validate(inst: Any) -> None: ...

# we use Any instead of _CountingAttr so that e.g. `make_class('Foo', [attr.ib()])` is valid
def make_class(name: str, attrs: Union[List[Any], Dict[str, Any]], bases: Tuple[type, ...] = ...,
               these: Optional[Dict[str, Any]] = ..., repr_ns: Optional[str] = ..., repr: bool = ..., cmp: bool = ..., hash: Optional[bool] = ..., init: bool = ..., slots: bool = ..., frozen: bool = ..., str: bool = ...) -> type: ...

# _funcs --
# FIXME: Overloads don't work.
#@overload
#def asdict(inst: Any, *, recurse: bool = ..., filter: Optional[_FilterType] = ..., dict_factory: Type[_M], retain_collection_types: bool = ...) -> _M: ...
#@overload
#def asdict(inst: Any, *, recurse: bool = ..., filter: Optional[_FilterType] = ..., retain_collection_types: bool = ...) -> Dict[str, Any]: ...

#@overload
#def astuple(inst: Any, *, recurse: bool = ..., filter: Optional[_FilterType] = ..., tuple_factory: Type[_I], retain_collection_types: bool = ...) -> _I: ...
#@overload
#def astuple(inst: Any, *, recurse: bool = ..., filter: Optional[_FilterType] = ..., retain_collection_types: bool = ...) -> Tuple[Any, ...]: ...

def has(cls: type) -> bool: ...
def assoc(inst: _T, **changes: Any) -> _T: ...
def evolve(inst: _T, **changes: Any) -> _T: ...

# _config --

def set_run_validators(run: bool) -> None: ...
def get_run_validators() -> bool: ...

# aliases
s = attrs = attributes
ib = attrib = attr

