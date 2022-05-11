import sys
import types
from _typeshed import Self
from abc import ABCMeta
from builtins import property as _builtins_property
from collections.abc import Iterable, Iterator, Mapping
from typing import Any, TypeVar, overload
from typing_extensions import Literal, TypeAlias

if sys.version_info >= (3, 11):
    __all__ = [
        "EnumType",
        "EnumMeta",
        "Enum",
        "IntEnum",
        "StrEnum",
        "Flag",
        "IntFlag",
        "ReprEnum",
        "auto",
        "unique",
        "property",
        "verify",
        "FlagBoundary",
        "STRICT",
        "CONFORM",
        "EJECT",
        "KEEP",
        "global_flag_repr",
        "global_enum_repr",
        "global_str",
        "global_enum",
        "EnumCheck",
        "CONTINUOUS",
        "NAMED_FLAGS",
        "UNIQUE",
    ]
else:
    __all__ = ["EnumMeta", "Enum", "IntEnum", "Flag", "IntFlag", "auto", "unique"]

_EnumMemberT = TypeVar("_EnumMemberT")
_EnumerationT = TypeVar("_EnumerationT", bound=type[Enum])

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
_EnumNames: TypeAlias = str | Iterable[str] | Iterable[Iterable[str | Any]] | Mapping[str, Any]

class _EnumDict(dict[str, Any]):
    def __init__(self) -> None: ...
    def __setitem__(self, key: str, value: Any) -> None: ...

# Note: EnumMeta actually subclasses type directly, not ABCMeta.
# This is a temporary workaround to allow multiple creation of enums with builtins
# such as str as mixins, which due to the handling of ABCs of builtin types, cause
# spurious inconsistent metaclass structure. See #1595.
# Structurally: Iterable[T], Reversible[T], Container[T] where T is the enum itself
class EnumMeta(ABCMeta):
    if sys.version_info >= (3, 11):
        def __new__(
            metacls: type[Self],  # type: ignore
            cls: str,
            bases: tuple[type, ...],
            classdict: _EnumDict,
            *,
            boundary: FlagBoundary | None = ...,
            _simple: bool = ...,
            **kwds: Any,
        ) -> Self: ...
    elif sys.version_info >= (3, 9):
        def __new__(metacls: type[Self], cls: str, bases: tuple[type, ...], classdict: _EnumDict, **kwds: Any) -> Self: ...  # type: ignore
    else:
        def __new__(metacls: type[Self], cls: str, bases: tuple[type, ...], classdict: _EnumDict) -> Self: ...  # type: ignore

    if sys.version_info >= (3, 9):
        @classmethod
        def __prepare__(metacls, cls: str, bases: tuple[type, ...], **kwds: Any) -> _EnumDict: ...  # type: ignore[override]
    else:
        @classmethod
        def __prepare__(metacls, cls: str, bases: tuple[type, ...]) -> _EnumDict: ...  # type: ignore[override]

    def __iter__(self: type[_EnumMemberT]) -> Iterator[_EnumMemberT]: ...
    def __reversed__(self: type[_EnumMemberT]) -> Iterator[_EnumMemberT]: ...
    def __contains__(self: type[Any], obj: object) -> bool: ...
    def __getitem__(self: type[_EnumMemberT], name: str) -> _EnumMemberT: ...
    @_builtins_property
    def __members__(self: type[_EnumMemberT]) -> types.MappingProxyType[str, _EnumMemberT]: ...
    def __len__(self) -> int: ...
    def __bool__(self) -> Literal[True]: ...
    # Simple value lookup
    @overload  # type: ignore[override]
    def __call__(cls: type[_EnumMemberT], value: Any, names: None = ...) -> _EnumMemberT: ...
    # Functional Enum API
    if sys.version_info >= (3, 11):
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
        ) -> type[Enum]: ...
    else:
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
        ) -> type[Enum]: ...
    _member_names_: list[str]  # undocumented
    _member_map_: dict[str, Enum]  # undocumented
    _value2member_map_: dict[Any, Enum]  # undocumented

if sys.version_info >= (3, 11):
    # In 3.11 `EnumMeta` metaclass is renamed to `EnumType`, but old name also exists.
    EnumType = EnumMeta

    class property(types.DynamicClassAttribute):
        def __set_name__(self, ownerclass: type[Enum], name: str) -> None: ...
        name: str
        clsname: str
    _magic_enum_attr = property
else:
    _magic_enum_attr = types.DynamicClassAttribute

class Enum(metaclass=EnumMeta):
    @_magic_enum_attr
    def name(self) -> str: ...
    @_magic_enum_attr
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
    def __new__(cls: type[Self], value: Any) -> Self: ...
    def __dir__(self) -> list[str]: ...
    def __format__(self, format_spec: str) -> str: ...
    def __hash__(self) -> Any: ...
    def __reduce_ex__(self, proto: object) -> Any: ...

if sys.version_info >= (3, 11):
    class ReprEnum(Enum): ...
    _IntEnumBase = ReprEnum
else:
    _IntEnumBase = Enum

class IntEnum(int, _IntEnumBase):
    _value_: int
    @_magic_enum_attr
    def value(self) -> int: ...
    def __new__(cls: type[Self], value: int) -> Self: ...

def unique(enumeration: _EnumerationT) -> _EnumerationT: ...

_auto_null: Any

# subclassing IntFlag so it picks up all implemented base functions, best modeling behavior of enum.auto()
class auto(IntFlag):
    _value_: Any
    @_magic_enum_attr
    def value(self) -> Any: ...
    def __new__(cls: type[Self]) -> Self: ...

class Flag(Enum):
    _name_: str | None  # type: ignore[assignment]
    _value_: int
    @_magic_enum_attr
    def name(self) -> str | None: ...  # type: ignore[override]
    @_magic_enum_attr
    def value(self) -> int: ...
    def __contains__(self: Self, other: Self) -> bool: ...
    def __bool__(self) -> bool: ...
    def __or__(self: Self, other: Self) -> Self: ...
    def __and__(self: Self, other: Self) -> Self: ...
    def __xor__(self: Self, other: Self) -> Self: ...
    def __invert__(self: Self) -> Self: ...

class IntFlag(int, Flag):
    def __new__(cls: type[Self], value: int) -> Self: ...
    def __or__(self: Self, other: int) -> Self: ...
    def __and__(self: Self, other: int) -> Self: ...
    def __xor__(self: Self, other: int) -> Self: ...
    def __ror__(self: Self, other: int) -> Self: ...
    def __rand__(self: Self, other: int) -> Self: ...
    def __rxor__(self: Self, other: int) -> Self: ...

if sys.version_info >= (3, 11):
    class StrEnum(str, ReprEnum):
        def __new__(cls: type[Self], value: str) -> Self: ...
        _value_: str
        @_magic_enum_attr
        def value(self) -> str: ...

    class EnumCheck(StrEnum):
        CONTINUOUS: str
        NAMED_FLAGS: str
        UNIQUE: str
    CONTINUOUS = EnumCheck.CONTINUOUS
    NAMED_FLAGS = EnumCheck.NAMED_FLAGS
    UNIQUE = EnumCheck.UNIQUE

    class verify:
        def __init__(self, *checks: EnumCheck) -> None: ...
        def __call__(self, enumeration: _EnumerationT) -> _EnumerationT: ...

    class FlagBoundary(StrEnum):
        STRICT: str
        CONFORM: str
        EJECT: str
        KEEP: str
    STRICT = FlagBoundary.STRICT
    CONFORM = FlagBoundary.CONFORM
    EJECT = FlagBoundary.EJECT
    KEEP = FlagBoundary.KEEP

    def global_str(self: Enum) -> str: ...
    def global_enum(cls: _EnumerationT, update_str: bool = ...) -> _EnumerationT: ...
    def global_enum_repr(self: Enum) -> str: ...
    def global_flag_repr(self: Flag) -> str: ...
