# Test stub for typing module that includes TypedDict `|` operator.
# It only covers `__or__`, `__ror__`, and `__ior__`.
#
# We cannot define these methods in `typing-typeddict.pyi`,
# because they need `dict` with two type args,
# and not all tests using `[typing typing-typeddict.pyi]` have the proper
# `dict` stub.
#
# Keep in sync with `typeshed`'s definition.
from abc import ABCMeta

cast = 0
assert_type = 0
overload = 0
Any = object()
Union = 0
Optional = 0
TypeVar = 0
Generic = 0
Protocol = 0
Tuple = 0
Callable = 0
NamedTuple = 0
Final = 0
Literal = 0
TypedDict = 0
NoReturn = 0
Required = 0
NotRequired = 0
Self = 0

T = TypeVar('T')
T_co = TypeVar('T_co', covariant=True)
V = TypeVar('V')

# Note: definitions below are different from typeshed, variances are declared
# to silence the protocol variance checks. Maybe it is better to use type: ignore?

class Sized(Protocol):
    def __len__(self) -> int: pass

class Iterable(Protocol[T_co]):
    def __iter__(self) -> 'Iterator[T_co]': pass

class Iterator(Iterable[T_co], Protocol):
    def __next__(self) -> T_co: pass

class Sequence(Iterable[T_co]):
    # misc is for explicit Any.
    def __getitem__(self, n: Any) -> T_co: pass # type: ignore[misc]

class Mapping(Iterable[T], Generic[T, T_co], metaclass=ABCMeta):
    pass

# Fallback type for all typed dicts (does not exist at runtime).
class _TypedDict(Mapping[str, object]):
    @overload
    def __or__(self, __value: Self) -> Self: ...
    @overload
    def __or__(self, __value: dict[str, Any]) -> dict[str, object]: ...
    @overload
    def __ror__(self, __value: Self) -> Self: ...
    @overload
    def __ror__(self, __value: dict[str, Any]) -> dict[str, object]: ...
    # supposedly incompatible definitions of __or__ and __ior__
    def __ior__(self, __value: Self) -> Self: ...  # type: ignore[misc]

class _SpecialForm: pass
