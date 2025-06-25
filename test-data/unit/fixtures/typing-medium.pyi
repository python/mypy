# More complete stub for typing module.
#
# Use [typing fixtures/typing-medium.pyi] to use this instead of lib-stub/typing.pyi
# in a particular test case.
#
# Many of the definitions have special handling in the type checker, so they
# can just be initialized to anything.

cast = 0
overload = 0
Any = object()
Union = 0
Optional = 0
TypeVar = 0
Generic = 0
Protocol = 0
Tuple = 0
Callable = 0
_promote = 0
NamedTuple = 0
Type = 0
no_type_check = 0
ClassVar = 0
Final = 0
Literal = 0
TypedDict = 0
NoReturn = 0
NewType = 0
TypeAlias = 0
LiteralString = 0
Self = 0

T = TypeVar('T')
T_co = TypeVar('T_co', covariant=True)
T_contra = TypeVar('T_contra', contravariant=True)
U = TypeVar('U')
V = TypeVar('V')
S = TypeVar('S')

# Note: definitions below are different from typeshed, variances are declared
# to silence the protocol variance checks. Maybe it is better to use type: ignore?

class Sized(Protocol):
    def __len__(self) -> int: pass

class Iterable(Protocol[T_co]):
    def __iter__(self) -> 'Iterator[T_co]': pass

class Iterator(Iterable[T_co], Protocol):
    def __next__(self) -> T_co: pass

class Generator(Iterator[T], Generic[T, U, V]):
    def __iter__(self) -> 'Generator[T, U, V]': pass

class Sequence(Iterable[T_co]):
    def __getitem__(self, n: Any) -> T_co: pass

class Mapping(Iterable[T], Generic[T, T_co]):
    def keys(self) -> Iterable[T]: pass  # Approximate return type
    def __getitem__(self, key: T) -> T_co: pass

class SupportsInt(Protocol):
    def __int__(self) -> int: pass

class SupportsFloat(Protocol):
    def __float__(self) -> float: pass

class ContextManager(Generic[T]):
    def __enter__(self) -> T: pass
    # Use Any because not all the precise types are in the fixtures.
    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> Any: pass

class _SpecialForm: pass

TYPE_CHECKING = 1
