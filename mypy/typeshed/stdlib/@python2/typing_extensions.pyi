import abc
from _typeshed import Self
from typing import (  # noqa: Y022
    TYPE_CHECKING as TYPE_CHECKING,
    Any,
    Callable,
    ClassVar as ClassVar,
    ContextManager as ContextManager,
    Counter as Counter,
    DefaultDict as DefaultDict,
    Deque as Deque,
    ItemsView,
    KeysView,
    Mapping,
    NewType as NewType,
    NoReturn as NoReturn,
    Protocol as Protocol,
    Text as Text,
    Type as Type,
    TypeVar,
    ValuesView,
    _Alias,
    overload as overload,
    runtime_checkable as runtime_checkable,
)

_T = TypeVar("_T")
_F = TypeVar("_F", bound=Callable[..., Any])

# unfortunately we have to duplicate this class definition from typing.pyi or we break pytype
class _SpecialForm:
    def __getitem__(self, typeargs: Any) -> object: ...

# This alias for above is kept here for backwards compatibility.
runtime = runtime_checkable
Final: _SpecialForm

def final(f: _F) -> _F: ...

Literal: _SpecialForm

def IntVar(name: str) -> Any: ...  # returns a new TypeVar

# Internal mypy fallback type for all typed dicts (does not exist at runtime)
class _TypedDict(Mapping[str, object], metaclass=abc.ABCMeta):
    def copy(self: Self) -> Self: ...
    # Using NoReturn so that only calls using mypy plugin hook that specialize the signature
    # can go through.
    def setdefault(self, k: NoReturn, default: object) -> object: ...
    def pop(self, k: NoReturn, default: _T = ...) -> object: ...
    def update(self: _T, __m: _T) -> None: ...
    def has_key(self, k: str) -> bool: ...
    def viewitems(self) -> ItemsView[str, object]: ...
    def viewkeys(self) -> KeysView[str]: ...
    def viewvalues(self) -> ValuesView[object]: ...
    def __delitem__(self, k: NoReturn) -> None: ...

# TypedDict is a (non-subscriptable) special form.
TypedDict: object

OrderedDict = _Alias()

def get_type_hints(
    obj: Callable[..., Any],
    globalns: dict[str, Any] | None = ...,
    localns: dict[str, Any] | None = ...,
    include_extras: bool = ...,
) -> dict[str, Any]: ...

Annotated: _SpecialForm
_AnnotatedAlias: Any  # undocumented

@runtime_checkable
class SupportsIndex(Protocol, metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def __index__(self) -> int: ...

# PEP 612 support for Python < 3.9
class ParamSpecArgs:
    __origin__: ParamSpec
    def __init__(self, origin: ParamSpec) -> None: ...

class ParamSpecKwargs:
    __origin__: ParamSpec
    def __init__(self, origin: ParamSpec) -> None: ...

class ParamSpec:
    __name__: str
    __bound__: type[Any] | None
    __covariant__: bool
    __contravariant__: bool
    def __init__(
        self, name: str, *, bound: None | type[Any] | str = ..., contravariant: bool = ..., covariant: bool = ...
    ) -> None: ...
    @property
    def args(self) -> ParamSpecArgs: ...
    @property
    def kwargs(self) -> ParamSpecKwargs: ...

Concatenate: _SpecialForm
TypeAlias: _SpecialForm
TypeGuard: _SpecialForm
