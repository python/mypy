# Stub for typing module. Many of the definitions have special handling in
# the type checker, so they can just be initialized to anything.
#
# DO NOT ADD TO THIS FILE UNLESS YOU HAVE A GOOD REASON! Additional definitions
# will slow down tests.
#
# Use [typing fixtures/typing-{medium,full,async,...}.pyi] in a test case for
# a more complete stub for typing. If you need to add things, add to one of
# the stubs under fixtures/.

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
Type = 0
ClassVar = 0
Final = 0
NoReturn = 0
Never = 0
NewType = 0
ParamSpec = 0
TypeVarTuple = 0
Unpack = 0
Self = 0
TYPE_CHECKING = 0

T = TypeVar('T')
T_co = TypeVar('T_co', covariant=True)
U = TypeVar('U')
V = TypeVar('V')

class Iterable(Protocol[T_co]):
    def __iter__(self) -> Iterator[T_co]: pass

class Iterator(Iterable[T_co], Protocol):
    def __next__(self) -> T_co: pass

class Generator(Iterator[T], Generic[T, U, V]):
    def __iter__(self) -> Generator[T, U, V]: pass

class Sequence(Iterable[T_co]):
    def __getitem__(self, n: Any) -> T_co: pass
    def __len__(self) -> int: pass

# Mapping type is oversimplified intentionally.
class Mapping(Iterable[T], Generic[T, T_co]):
    def keys(self) -> Iterable[T]: pass  # Approximate return type
    def __getitem__(self, key: T) -> T_co: pass

class Awaitable(Protocol[T]):
    def __await__(self) -> Generator[Any, Any, T]: pass

class Coroutine(Awaitable[V], Generic[T, U, V]): pass

def final(meth: T) -> T: pass

def reveal_type(__obj: T) -> T: pass

class _SpecialForm: pass
