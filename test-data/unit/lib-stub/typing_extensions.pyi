import typing
from typing import Any, Callable, Mapping, Iterable, Iterator, NoReturn as NoReturn, Dict, Tuple, Type, Union
from typing import TYPE_CHECKING as TYPE_CHECKING
from typing import NewType as NewType, overload as overload

import sys

_T = typing.TypeVar('_T')

class _SpecialForm:
    def __getitem__(self, typeargs: Any) -> Any:
        pass

    def __call__(self, arg: Any) -> Any:
        pass

NamedTuple = 0
Protocol: _SpecialForm = ...
def runtime_checkable(x: _T) -> _T: pass
runtime = runtime_checkable

Final: _SpecialForm = ...
def final(x: _T) -> _T: pass

Literal: _SpecialForm = ...

Annotated: _SpecialForm = ...

TypeVar: _SpecialForm

ParamSpec: _SpecialForm
Concatenate: _SpecialForm

TypeAlias: _SpecialForm

TypeGuard: _SpecialForm
TypeIs: _SpecialForm
Never: _SpecialForm

TypeVarTuple: _SpecialForm
Unpack: _SpecialForm
Required: _SpecialForm
NotRequired: _SpecialForm
ReadOnly: _SpecialForm

@final
class TypeAliasType:
    def __init__(
        self, name: str, value: Any, *, type_params: Tuple[Union[TypeVar, ParamSpec, TypeVarTuple], ...] = ()
    ) -> None: ...

# Fallback type for all typed dicts (does not exist at runtime).
class _TypedDict(Mapping[str, object]):
    # Needed to make this class non-abstract. It is explicitly declared abstract in
    # typeshed, but we don't want to import abc here, as it would slow down the tests.
    def __iter__(self) -> Iterator[str]: ...
    def copy(self: _T) -> _T: ...
    # Using NoReturn so that only calls using the plugin hook can go through.
    def setdefault(self, k: NoReturn, default: object) -> object: ...
    # Mypy expects that 'default' has a type variable type.
    def pop(self, k: NoReturn, default: _T = ...) -> object: ...
    def update(self: _T, __m: _T) -> None: ...
    def items(self) -> Iterable[Tuple[str, object]]: ...
    def keys(self) -> Iterable[str]: ...
    def values(self) -> Iterable[object]: ...
    if sys.version_info < (3, 0):
        def has_key(self, k: str) -> bool: ...
    def __delitem__(self, k: NoReturn) -> None: ...
    # Stubtest's tests need the following items:
    __required_keys__: frozenset[str]
    __optional_keys__: frozenset[str]
    __readonly_keys__: frozenset[str]
    __mutable_keys__: frozenset[str]
    __closed__: bool
    __extra_items__: Any
    __total__: bool

def TypedDict(typename: str, fields: Dict[str, Type[_T]], *, total: Any = ...) -> Type[dict]: ...

def reveal_type(__obj: _T) -> _T: pass
def assert_type(__val: _T, __typ: Any) -> _T: pass

def dataclass_transform(
    *,
    eq_default: bool = ...,
    order_default: bool = ...,
    kw_only_default: bool = ...,
    field_specifiers: tuple[type[Any] | Callable[..., Any], ...] = ...,
    **kwargs: Any,
) -> Callable[[_T], _T]: ...

def override(__arg: _T) -> _T: ...
def deprecated(__msg: str) -> Callable[[_T], _T]: ...

_FutureFeatureFixture = 0
