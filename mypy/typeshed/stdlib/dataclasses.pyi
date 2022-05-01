import enum
import sys
import types
from builtins import type as Type  # alias to avoid name clashes with fields named "type"
from collections.abc import Callable, Iterable, Mapping
from typing import Any, Generic, Protocol, TypeVar, overload
from typing_extensions import Literal

if sys.version_info >= (3, 9):
    from types import GenericAlias

_T = TypeVar("_T")
_T_co = TypeVar("_T_co", covariant=True)

if sys.version_info >= (3, 10):
    __all__ = [
        "dataclass",
        "field",
        "Field",
        "FrozenInstanceError",
        "InitVar",
        "KW_ONLY",
        "MISSING",
        "fields",
        "asdict",
        "astuple",
        "make_dataclass",
        "replace",
        "is_dataclass",
    ]
else:
    __all__ = [
        "dataclass",
        "field",
        "Field",
        "FrozenInstanceError",
        "InitVar",
        "MISSING",
        "fields",
        "asdict",
        "astuple",
        "make_dataclass",
        "replace",
        "is_dataclass",
    ]

# define _MISSING_TYPE as an enum within the type stubs,
# even though that is not really its type at runtime
# this allows us to use Literal[_MISSING_TYPE.MISSING]
# for background, see:
#   https://github.com/python/typeshed/pull/5900#issuecomment-895513797
class _MISSING_TYPE(enum.Enum):
    MISSING = enum.auto()

MISSING = _MISSING_TYPE.MISSING

if sys.version_info >= (3, 10):
    class KW_ONLY: ...

@overload
def asdict(obj: Any) -> dict[str, Any]: ...
@overload
def asdict(obj: Any, *, dict_factory: Callable[[list[tuple[str, Any]]], _T]) -> _T: ...
@overload
def astuple(obj: Any) -> tuple[Any, ...]: ...
@overload
def astuple(obj: Any, *, tuple_factory: Callable[[list[Any]], _T]) -> _T: ...

if sys.version_info >= (3, 8):
    # cls argument is now positional-only
    @overload
    def dataclass(__cls: type[_T]) -> type[_T]: ...
    @overload
    def dataclass(__cls: None) -> Callable[[type[_T]], type[_T]]: ...

else:
    @overload
    def dataclass(_cls: type[_T]) -> type[_T]: ...
    @overload
    def dataclass(_cls: None) -> Callable[[type[_T]], type[_T]]: ...

if sys.version_info >= (3, 10):
    @overload
    def dataclass(
        *,
        init: bool = ...,
        repr: bool = ...,
        eq: bool = ...,
        order: bool = ...,
        unsafe_hash: bool = ...,
        frozen: bool = ...,
        match_args: bool = ...,
        kw_only: bool = ...,
        slots: bool = ...,
    ) -> Callable[[type[_T]], type[_T]]: ...

else:
    @overload
    def dataclass(
        *, init: bool = ..., repr: bool = ..., eq: bool = ..., order: bool = ..., unsafe_hash: bool = ..., frozen: bool = ...
    ) -> Callable[[type[_T]], type[_T]]: ...

# See https://github.com/python/mypy/issues/10750
class _DefaultFactory(Protocol[_T_co]):
    def __call__(self) -> _T_co: ...

class Field(Generic[_T]):
    name: str
    type: Type[_T]
    default: _T | Literal[_MISSING_TYPE.MISSING]
    default_factory: _DefaultFactory[_T] | Literal[_MISSING_TYPE.MISSING]
    repr: bool
    hash: bool | None
    init: bool
    compare: bool
    metadata: types.MappingProxyType[Any, Any]
    if sys.version_info >= (3, 10):
        kw_only: bool | Literal[_MISSING_TYPE.MISSING]
        def __init__(
            self,
            default: _T,
            default_factory: Callable[[], _T],
            init: bool,
            repr: bool,
            hash: bool | None,
            compare: bool,
            metadata: Mapping[Any, Any],
            kw_only: bool,
        ) -> None: ...
    else:
        def __init__(
            self,
            default: _T,
            default_factory: Callable[[], _T],
            init: bool,
            repr: bool,
            hash: bool | None,
            compare: bool,
            metadata: Mapping[Any, Any],
        ) -> None: ...

    def __set_name__(self, owner: Type[Any], name: str) -> None: ...
    if sys.version_info >= (3, 9):
        def __class_getitem__(cls, item: Any) -> GenericAlias: ...

# NOTE: Actual return type is 'Field[_T]', but we want to help type checkers
# to understand the magic that happens at runtime.
if sys.version_info >= (3, 10):
    @overload  # `default` and `default_factory` are optional and mutually exclusive.
    def field(
        *,
        default: _T,
        init: bool = ...,
        repr: bool = ...,
        hash: bool | None = ...,
        compare: bool = ...,
        metadata: Mapping[Any, Any] | None = ...,
        kw_only: bool = ...,
    ) -> _T: ...
    @overload
    def field(
        *,
        default_factory: Callable[[], _T],
        init: bool = ...,
        repr: bool = ...,
        hash: bool | None = ...,
        compare: bool = ...,
        metadata: Mapping[Any, Any] | None = ...,
        kw_only: bool = ...,
    ) -> _T: ...
    @overload
    def field(
        *,
        init: bool = ...,
        repr: bool = ...,
        hash: bool | None = ...,
        compare: bool = ...,
        metadata: Mapping[Any, Any] | None = ...,
        kw_only: bool = ...,
    ) -> Any: ...

else:
    @overload  # `default` and `default_factory` are optional and mutually exclusive.
    def field(
        *,
        default: _T,
        init: bool = ...,
        repr: bool = ...,
        hash: bool | None = ...,
        compare: bool = ...,
        metadata: Mapping[Any, Any] | None = ...,
    ) -> _T: ...
    @overload
    def field(
        *,
        default_factory: Callable[[], _T],
        init: bool = ...,
        repr: bool = ...,
        hash: bool | None = ...,
        compare: bool = ...,
        metadata: Mapping[Any, Any] | None = ...,
    ) -> _T: ...
    @overload
    def field(
        *,
        init: bool = ...,
        repr: bool = ...,
        hash: bool | None = ...,
        compare: bool = ...,
        metadata: Mapping[Any, Any] | None = ...,
    ) -> Any: ...

def fields(class_or_instance: Any) -> tuple[Field[Any], ...]: ...
def is_dataclass(obj: Any) -> bool: ...

class FrozenInstanceError(AttributeError): ...

class InitVar(Generic[_T]):
    type: Type[_T]
    def __init__(self, type: Type[_T]) -> None: ...
    if sys.version_info >= (3, 9):
        @overload
        def __class_getitem__(cls, type: Type[_T]) -> InitVar[_T]: ...
        @overload
        def __class_getitem__(cls, type: Any) -> InitVar[Any]: ...

if sys.version_info >= (3, 10):
    def make_dataclass(
        cls_name: str,
        fields: Iterable[str | tuple[str, type] | tuple[str, type, Field[Any]]],
        *,
        bases: tuple[type, ...] = ...,
        namespace: dict[str, Any] | None = ...,
        init: bool = ...,
        repr: bool = ...,
        eq: bool = ...,
        order: bool = ...,
        unsafe_hash: bool = ...,
        frozen: bool = ...,
        match_args: bool = ...,
        kw_only: bool = ...,
        slots: bool = ...,
    ) -> type: ...

else:
    def make_dataclass(
        cls_name: str,
        fields: Iterable[str | tuple[str, type] | tuple[str, type, Field[Any]]],
        *,
        bases: tuple[type, ...] = ...,
        namespace: dict[str, Any] | None = ...,
        init: bool = ...,
        repr: bool = ...,
        eq: bool = ...,
        order: bool = ...,
        unsafe_hash: bool = ...,
        frozen: bool = ...,
    ) -> type: ...

def replace(__obj: _T, **changes: Any) -> _T: ...
