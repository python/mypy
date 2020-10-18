from typing import TypeVar, overload, Callable, Any, Type, Optional, Union, Sequence, Mapping

_T = TypeVar('_T')
_C = TypeVar('_C', bound=type)

_ValidatorType = Callable[[Any, Any, _T], Any]
_ConverterType = Callable[[Any], _T]
_FilterType = Callable[[Any, Any], bool]
_ValidatorArgType = Union[_ValidatorType[_T], Sequence[_ValidatorType[_T]]]

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
