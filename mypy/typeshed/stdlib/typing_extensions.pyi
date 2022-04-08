import abc
import sys
from _typeshed import Self as TypeshedSelf  # see #6932 for why the alias cannot have a leading underscore
from typing import (  # noqa: Y022,Y027
    TYPE_CHECKING as TYPE_CHECKING,
    Any,
    AsyncContextManager as AsyncContextManager,
    AsyncGenerator as AsyncGenerator,
    AsyncIterable as AsyncIterable,
    AsyncIterator as AsyncIterator,
    Awaitable as Awaitable,
    Callable,
    ChainMap as ChainMap,
    ClassVar as ClassVar,
    ContextManager as ContextManager,
    Coroutine as Coroutine,
    Counter as Counter,
    DefaultDict as DefaultDict,
    Deque as Deque,
    ItemsView,
    KeysView,
    Mapping,
    NewType as NewType,
    NoReturn as NoReturn,
    Text as Text,
    Type as Type,
    TypeVar,
    ValuesView,
    _Alias,
    overload as overload,
)

_T = TypeVar("_T")
_F = TypeVar("_F", bound=Callable[..., Any])
_TC = TypeVar("_TC", bound=Type[object])

# unfortunately we have to duplicate this class definition from typing.pyi or we break pytype
class _SpecialForm:
    def __getitem__(self, parameters: Any) -> object: ...
    if sys.version_info >= (3, 10):
        def __or__(self, other: Any) -> _SpecialForm: ...
        def __ror__(self, other: Any) -> _SpecialForm: ...

# Do not import (and re-export) Protocol or runtime_checkable from
# typing module because type checkers need to be able to distinguish
# typing.Protocol and typing_extensions.Protocol so they can properly
# warn users about potential runtime exceptions when using typing.Protocol
# on older versions of Python.
Protocol: _SpecialForm = ...

def runtime_checkable(cls: _TC) -> _TC: ...

# This alias for above is kept here for backwards compatibility.
runtime = runtime_checkable
Final: _SpecialForm

def final(f: _F) -> _F: ...

Literal: _SpecialForm

def IntVar(name: str) -> Any: ...  # returns a new TypeVar

# Internal mypy fallback type for all typed dicts (does not exist at runtime)
class _TypedDict(Mapping[str, object], metaclass=abc.ABCMeta):
    __required_keys__: frozenset[str]
    __optional_keys__: frozenset[str]
    __total__: bool
    def copy(self: TypeshedSelf) -> TypeshedSelf: ...
    # Using NoReturn so that only calls using mypy plugin hook that specialize the signature
    # can go through.
    def setdefault(self, k: NoReturn, default: object) -> object: ...
    # Mypy plugin hook for 'pop' expects that 'default' has a type variable type.
    def pop(self, k: NoReturn, default: _T = ...) -> object: ...  # type: ignore
    def update(self: _T, __m: _T) -> None: ...
    def items(self) -> ItemsView[str, object]: ...
    def keys(self) -> KeysView[str]: ...
    def values(self) -> ValuesView[object]: ...
    def __delitem__(self, k: NoReturn) -> None: ...

# TypedDict is a (non-subscriptable) special form.
TypedDict: object

OrderedDict = _Alias()

if sys.version_info >= (3, 7):
    def get_type_hints(
        obj: Callable[..., Any],
        globalns: dict[str, Any] | None = ...,
        localns: dict[str, Any] | None = ...,
        include_extras: bool = ...,
    ) -> dict[str, Any]: ...
    def get_args(tp: Any) -> tuple[Any, ...]: ...
    def get_origin(tp: Any) -> Any | None: ...

Annotated: _SpecialForm
_AnnotatedAlias: Any  # undocumented

@runtime_checkable
class SupportsIndex(Protocol, metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def __index__(self) -> int: ...

# New things in 3.10
if sys.version_info >= (3, 10):
    from typing import (
        Concatenate as Concatenate,
        ParamSpec as ParamSpec,
        TypeAlias as TypeAlias,
        TypeGuard as TypeGuard,
        is_typeddict as is_typeddict,
    )
else:
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
    def is_typeddict(tp: object) -> bool: ...

# New things in 3.11
if sys.version_info >= (3, 11):
    from typing import Never as Never, Self as Self, assert_never as assert_never, reveal_type as reveal_type
else:
    Self: _SpecialForm
    Never: _SpecialForm
    def reveal_type(__obj: _T) -> _T: ...
    def assert_never(__arg: NoReturn) -> NoReturn: ...

# Experimental (hopefully these will be in 3.11)
Required: _SpecialForm
NotRequired: _SpecialForm
LiteralString: _SpecialForm
Unpack: _SpecialForm

@final
class TypeVarTuple:
    __name__: str
    def __init__(self, name: str) -> None: ...
    def __iter__(self) -> Any: ...  # Unpack[Self]

def dataclass_transform(
    *,
    eq_default: bool = ...,
    order_default: bool = ...,
    kw_only_default: bool = ...,
    field_descriptors: tuple[type[Any] | Callable[..., Any], ...] = ...,
) -> Callable[[_T], _T]: ...
