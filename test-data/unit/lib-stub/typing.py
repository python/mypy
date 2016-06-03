# Stub for typing module. Many of the definitions have special handling in
# the type checker, so they can just be initialized to anything.

from abc import abstractmethod

cast = 0
overload = 0
Any = 0
Union = 0
Optional = 0
TypeVar = 0
Generic = 0
Tuple = 0
Callable = 0
builtinclass = 0
_promote = 0
NamedTuple = 0
Type = 0
no_type_check = 0

# Type aliases.
List = 0
Dict = 0
Set = 0

T = TypeVar('T')
U = TypeVar('U')
V = TypeVar('V')

class Container(Generic[T]):
    @abstractmethod
    # Use int because bool isn't in the default test builtins
    def __contains__(self, arg: T) -> int: pass

class Sized:
    @abstractmethod
    def __len__(self) -> int: pass

class Iterable(Generic[T]):
    @abstractmethod
    def __iter__(self) -> 'Iterator[T]': pass

class Iterator(Iterable[T], Generic[T]):
    @abstractmethod
    def __next__(self) -> T: pass

class Generator(Iterator[T], Generic[T, U, V]):
    @abstractmethod
    def send(self, value: U) -> T: pass

    @abstractmethod
    def throw(self, typ: Any, val: Any=None, tb=None) -> None: pass

    @abstractmethod
    def close(self) -> None: pass

    @abstractmethod
    def __iter__(self) -> 'Generator[T, U, V]': pass

class Awaitable(Generic[T]):
    @abstractmethod
    def __await__(self) -> Generator[Any, Any, T]: pass

class Sequence(Generic[T]):
    @abstractmethod
    def __getitem__(self, n: Any) -> T: pass
