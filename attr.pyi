from typing import Any, Callable, Collection, Dict, Generic, List, Optional, Mapping, Tuple, Type, TypeVar, Union, overload, Sequence
# `import X as X` is required to expose these to mypy. otherwise they are invisible
#from . import exceptions as exceptions
#from . import filters as filters
#from . import converters as converters
#from . import validators as validators

# typing --

_T = TypeVar('_T')
_C = TypeVar('_C', bound=type)
_M = TypeVar('_M', bound=Mapping)
_I = TypeVar('_I', bound=Collection)

_ValidatorType = Callable[[Any, 'Attribute', _T], Any]
_ConverterType = Callable[[Any], _T]
_FilterType = Callable[['Attribute', Any], bool]
_ValidatorArgType = Union[_ValidatorType[_T], Sequence[_ValidatorType[_T]]]

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


# `attr` also lies about its return type to make the following possible:
#     attr()    -> Any
#     attr(8)   -> int
#     attr(validator=<some callable>)  -> Whatever the callable expects.
# This makes this type of assignments possible:
#     x: int = attr(8)
#
# 1st form catches a default value set.  Can't use = ... or you get "overloaded overlap" error.
@overload
def attr(default: _T, validator: Optional[_ValidatorArgType[_T]] = ...,
         repr: bool = ..., cmp: bool = ..., hash: Optional[bool] = ..., init: bool = ...,
         convert: _ConverterType[_T] = ..., metadata: Mapping = ...,
         type: Type[_T] = ...) -> _T: ...
@overload
def attr(default: Optional[_T] = ..., validator: Optional[_ValidatorArgType[_T]] = ...,
         repr: bool = ..., cmp: bool = ..., hash: Optional[bool] = ..., init: bool = ...,
         convert: _ConverterType[_T] = ..., metadata: Mapping = ...,
         type: Type[_T] = ...) -> _T: ...
# 3rd form catches nothing set. So returns Any.
@overload
def attr(default: None = ..., validator: None = ...,
         repr: bool = ..., cmp: bool = ..., hash: Optional[bool] = ..., init: bool = ...,
         convert: None = ..., metadata: Mapping = ...,
         type: None = ...) -> Any: ...


@overload
def attributes(maybe_cls: _C, these: Optional[Dict[str, Any]] = ..., repr_ns: Optional[str] = ..., repr: bool = ..., cmp: bool = ..., hash: Optional[bool] = ..., init: bool = ..., slots: bool = ..., frozen: bool = ..., str: bool = ...) -> _C: ...
@overload
def attributes(maybe_cls: None = ..., these: Optional[Dict[str, Any]] = ..., repr_ns: Optional[str] = ..., repr: bool = ..., cmp: bool = ..., hash: Optional[bool] = ..., init: bool = ..., slots: bool = ..., frozen: bool = ..., str: bool = ...) -> Callable[[_C], _C]: ...

def fields(cls: type) -> Tuple[Attribute, ...]: ...
def validate(inst: Any) -> None: ...

# we use Any instead of _CountingAttr so that e.g. `make_class('Foo', [attr.ib()])` is valid
def make_class(name, attrs: Union[List[str], Dict[str, Any]], bases: Tuple[type, ...] = ..., **attributes_arguments) -> type: ...

# _funcs --

# FIXME: asdict/astuple do not honor their factory args.  waiting on one of these:
# https://github.com/python/mypy/issues/4236
# https://github.com/python/typing/issues/253
def asdict(inst: Any, *, recurse: bool = ..., filter: Optional[_FilterType] = ..., dict_factory: Type[Mapping] = ..., retain_collection_types: bool = ...) -> Dict[str, Any]: ...

# @overload
# def asdict(inst: Any, *, recurse: bool = ..., filter: Optional[_FilterType] = ..., dict_factory: Type[_M], retain_collection_types: bool = ...) -> _M: ...
# @overload
# def asdict(inst: Any, *, recurse: bool = ..., filter: Optional[_FilterType] = ..., retain_collection_types: bool = ...) -> Dict[str, Any]: ...

def astuple(inst: Any, *, recurse: bool = ..., filter: Optional[_FilterType] = ..., tuple_factory: Type[Collection] = ..., retain_collection_types: bool = ...) -> Tuple[Any, ...]: ...

# @overload
# def astuple(inst: Any, *, recurse: bool = ..., filter: Optional[_FilterType] = ..., tuple_factory: Type[_I], retain_collection_types: bool = ...) -> _I: ...
# @overload
# def astuple(inst: Any, *, recurse: bool = ..., filter: Optional[_FilterType] = ..., retain_collection_types: bool = ...) -> tuple: ...

def has(cls: type) -> bool: ...
def assoc(inst: _T, **changes) -> _T: ...
def evolve(inst: _T, **changes) -> _T: ...

# _config --

def set_run_validators(run: bool) -> None: ...
def get_run_validators() -> bool: ...

# aliases
s = attrs = attributes
ib = attrib = attr
