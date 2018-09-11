# Stub for typing module. Many of the definitions have special handling in
# the type checker, so they can just be initialized to anything.

cast = 0
overload = 0
Any = 0
Union = 0
Optional = 0
TypeVar = 0
Generic = 0
Protocol = 0  # This is not yet defined in typeshed, see PR typeshed/#1220
Tuple = 0
Callable = 0
_promote = 0
NamedTuple = 0
Type = 0
no_type_check = 0
ClassVar = 0
Final = 0
NoReturn = 0
NewType = 0

# Type aliases.
List = 0
Dict = 0
Set = 0

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

@runtime
class Iterable(Protocol[T_co]):
    def __iter__(self) -> 'Iterator[T_co]': pass

class Iterator(Iterable[T_co], Protocol):
    def __next__(self) -> T_co: pass

class Generator(Iterator[T], Generic[T, U, V]):
    def __iter__(self) -> 'Generator[T, U, V]': pass

class Sequence(Iterable[T_co]):
    def __getitem__(self, n: Any) -> T_co: pass

class Mapping(Generic[T_contra, T_co]):
    def __getitem__(self, key: T_contra) -> T_co: pass

def runtime(cls: type) -> type: pass

# This is an unofficial extension.
def final(meth: T) -> T: pass

TYPE_CHECKING = 1
