# Stub for typing module. Many of the definitions have special handling in
# the type checker, so they can just be initialized to anything.

from abc import abstractmethod

class GenericMeta(type): pass

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

@runtime
class Container(Protocol[T_contra]):
    @abstractmethod
    # Use int because bool isn't in the default test builtins
    def __contains__(self, arg: T_contra) -> int: pass

@runtime
class Sized(Protocol):
    @abstractmethod
    def __len__(self) -> int: pass

@runtime
class Iterable(Protocol[T_co]):
    @abstractmethod
    def __iter__(self) -> 'Iterator[T_co]': pass

@runtime
class Iterator(Iterable[T_co], Protocol):
    @abstractmethod
    def __next__(self) -> T_co: pass

class Generator(Iterator[T], Generic[T, U, V]):
    @abstractmethod
    def __iter__(self) -> 'Generator[T, U, V]': pass

@runtime
class Sequence(Iterable[T_co], Protocol):
    @abstractmethod
    def __getitem__(self, n: Any) -> T_co: pass

@runtime
class Mapping(Protocol[T_contra, T_co]):
    def __getitem__(self, key: T_contra) -> T_co: pass

@runtime
class MutableMapping(Mapping[T_contra, U], Protocol):
    def __setitem__(self, k: T_contra, v: U) -> None: pass

class SupportsInt(Protocol):
    def __int__(self) -> int: pass

def runtime(cls: T) -> T:
    return cls

TYPE_CHECKING = 1
