import sys
import types
from abc import ABCMeta
from builtins import property as _builtins_property
from collections.abc import Iterable, Iterator, Mapping
from typing import Any, Type, TypeVar, Union, overload

_T = TypeVar("_T")
_S = TypeVar("_S", bound=Type[Enum])

# The following all work:
# >>> from enum import Enum
# >>> from string import ascii_lowercase
# >>> Enum('Foo', names='RED YELLOW GREEN')
# <enum 'Foo'>
# >>> Enum('Foo', names=[('RED', 1), ('YELLOW, 2)])
# <enum 'Foo'>
# >>> Enum('Foo', names=((x for x in (ascii_lowercase[i], i)) for i in range(5)))
# <enum 'Foo'>
# >>> Enum('Foo', names={'RED': 1, 'YELLOW': 2})
# <enum 'Foo'>
_EnumNames = Union[str, Iterable[str], Iterable[Iterable[Union[str, Any]]], Mapping[str, Any]]

class _EnumDict(dict[str, Any]):
    def __init__(self) -> None: ...

# Note: EnumMeta actually subclasses type directly, not ABCMeta.
# This is a temporary workaround to allow multiple creation of enums with builtins
# such as str as mixins, which due to the handling of ABCs of builtin types, cause
# spurious inconsistent metaclass structure. See #1595.
# Structurally: Iterable[T], Reversible[T], Container[T] where T is the enum itself
class EnumMeta(ABCMeta):
    if sys.version_info >= (3, 11):
        def __new__(
            metacls: Type[_T],
            cls: str,
            bases: tuple[type, ...],
            classdict: _EnumDict,
            *,
            boundary: FlagBoundary | None = ...,
            _simple: bool = ...,
            **kwds: Any,
        ) -> _T: ...
    elif sys.version_info >= (3, 9):
        def __new__(metacls: Type[_T], cls: str, bases: tuple[type, ...], classdict: _EnumDict, **kwds: Any) -> _T: ...  # type: ignore
    else:
        def __new__(metacls: Type[_T], cls: str, bases: tuple[type, ...], classdict: _EnumDict) -> _T: ...  # type: ignore
    def __iter__(self: Type[_T]) -> Iterator[_T]: ...
    def __reversed__(self: Type[_T]) -> Iterator[_T]: ...
    def __contains__(self: Type[Any], member: object) -> bool: ...
    def __getitem__(self: Type[_T], name: str) -> _T: ...
    @_builtins_property
    def __members__(self: Type[_T]) -> types.MappingProxyType[str, _T]: ...
    def __len__(self) -> int: ...
    if sys.version_info >= (3, 11):
        # Simple value lookup
        @overload  # type: ignore[override]
        def __call__(cls: Type[_T], value: Any, names: None = ...) -> _T: ...
        # Functional Enum API
        @overload
        def __call__(
            cls,
            value: str,
            names: _EnumNames,
            *,
            module: str | None = ...,
            qualname: str | None = ...,
            type: type | None = ...,
            start: int = ...,
            boundary: FlagBoundary | None = ...,
        ) -> Type[Enum]: ...
    else:
        @overload  # type: ignore[override]
        def __call__(cls: Type[_T], value: Any, names: None = ...) -> _T: ...
        @overload
        def __call__(
            cls,
            value: str,
            names: _EnumNames,
            *,
            module: str | None = ...,
            qualname: str | None = ...,
            type: type | None = ...,
            start: int = ...,
        ) -> Type[Enum]: ...
    _member_names_: list[str]  # undocumented
    _member_map_: dict[str, Enum]  # undocumented
    _value2member_map_: dict[Any, Enum]  # undocumented

if sys.version_info >= (3, 11):
    # In 3.11 `EnumMeta` metaclass is renamed to `EnumType`, but old name also exists.
    EnumType = EnumMeta

class Enum(metaclass=EnumMeta):
    if sys.version_info >= (3, 11):
        @property
        def name(self) -> str: ...
        @property
        def value(self) -> Any: ...
    else:
        @types.DynamicClassAttribute
        def name(self) -> str: ...
        @types.DynamicClassAttribute
        def value(self) -> Any: ...
    _name_: str
    _value_: Any
    if sys.version_info >= (3, 7):
        _ignore_: str | list[str]
    _order_: str
    __order__: str
    @classmethod
    def _missing_(cls, value: object) -> Any: ...
    @staticmethod
    def _generate_next_value_(name: str, start: int, count: int, last_values: list[Any]) -> Any: ...
    def __new__(cls: Type[_T], value: object) -> _T: ...
    def __repr__(self) -> str: ...
    def __str__(self) -> str: ...
    def __dir__(self) -> list[str]: ...
    def __format__(self, format_spec: str) -> str: ...
    def __hash__(self) -> Any: ...
    def __reduce_ex__(self, proto: object) -> Any: ...

class IntEnum(int, Enum):
    _value_: int
    if sys.version_info >= (3, 11):
        @property
        def value(self) -> int: ...
    else:
        @types.DynamicClassAttribute
        def value(self) -> int: ...
    def __new__(cls: Type[_T], value: int | _T) -> _T: ...

def unique(enumeration: _S) -> _S: ...

_auto_null: Any

# subclassing IntFlag so it picks up all implemented base functions, best modeling behavior of enum.auto()
class auto(IntFlag):
    _value_: Any
    if sys.version_info >= (3, 11):
        @property
        def value(self) -> Any: ...
    else:
        @types.DynamicClassAttribute
        def value(self) -> Any: ...
    def __new__(cls: Type[_T]) -> _T: ...

class Flag(Enum):
    _name_: str | None  # type: ignore[assignment]
    _value_: int
    if sys.version_info >= (3, 11):
        @property
        def name(self) -> str | None: ...  # type: ignore[override]
        @property
        def value(self) -> int: ...
    else:
        @types.DynamicClassAttribute
        def name(self) -> str | None: ...  # type: ignore[override]
        @types.DynamicClassAttribute
        def value(self) -> int: ...
    def __contains__(self: _T, other: _T) -> bool: ...
    def __repr__(self) -> str: ...
    def __str__(self) -> str: ...
    def __bool__(self) -> bool: ...
    def __or__(self: _T, other: _T) -> _T: ...
    def __and__(self: _T, other: _T) -> _T: ...
    def __xor__(self: _T, other: _T) -> _T: ...
    def __invert__(self: _T) -> _T: ...

class IntFlag(int, Flag):
    def __new__(cls: Type[_T], value: int | _T) -> _T: ...
    def __or__(self: _T, other: int | _T) -> _T: ...
    def __and__(self: _T, other: int | _T) -> _T: ...
    def __xor__(self: _T, other: int | _T) -> _T: ...
    def __ror__(self: _T, n: int | _T) -> _T: ...
    def __rand__(self: _T, n: int | _T) -> _T: ...
    def __rxor__(self: _T, n: int | _T) -> _T: ...

if sys.version_info >= (3, 11):
    class StrEnum(str, Enum):
        def __new__(cls: Type[_T], value: str | _T) -> _T: ...
        _value_: str
        @property
        def value(self) -> str: ...
    class FlagBoundary(StrEnum):
        STRICT: str
        CONFORM: str
        EJECT: str
        KEEP: str
    STRICT = FlagBoundary.STRICT
    CONFORM = FlagBoundary.CONFORM
    EJECT = FlagBoundary.EJECT
    KEEP = FlagBoundary.KEEP
    class property(types.DynamicClassAttribute):
        def __set_name__(self, ownerclass: Type[Enum], name: str) -> None: ...
        name: str
        clsname: str
    def global_enum(cls: _S) -> _S: ...
    def global_enum_repr(self: Enum) -> str: ...
    def global_flag_repr(self: Flag) -> str: ...
