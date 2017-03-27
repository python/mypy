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
ClassVar = 0
Protocol = 0

# Type aliases.
List = 0
Dict = 0
Set = 0

T = TypeVar('T')
U = TypeVar('U')
V = TypeVar('V')
S = TypeVar('S')

@runtime
class Container(Protocol[T]):
    @abstractmethod
    # Use int because bool isn't in the default test builtins
    def __contains__(self, arg: T) -> int: pass

@runtime
class Sized(Protocol):
    @abstractmethod
    def __len__(self) -> int: pass

@runtime
class Iterable(Protocol[T]):
    @abstractmethod
    def __iter__(self) -> 'Iterator[T]': pass

@runtime
class Iterator(Iterable[T], Protocol):
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

class AsyncGenerator(AsyncIterator[T], Generic[T, U]):
    @abstractmethod
    def __anext__(self) -> Awaitable[T]: pass

    @abstractmethod
    def asend(self, value: U) -> Awaitable[T]: pass

    @abstractmethod
    def athrow(self, typ: Any, val: Any=None, tb: Any=None) -> Awaitable[T]: pass

    @abstractmethod
    def aclose(self) -> Awaitable[T]: pass

    @abstractmethod
    def __aiter__(self) -> 'AsyncGenerator[T, U]': pass

@runtime
class Awaitable(Protocol[T]):
    @abstractmethod
    def __await__(self) -> Generator[Any, Any, T]: pass

class AwaitableGenerator(Generator[T, U, V], Awaitable[V], Generic[T, U, V, S]):
    pass

@runtime
class AsyncIterable(Protocol[T]):
    @abstractmethod
    def __aiter__(self) -> 'AsyncIterator[T]': pass

@runtime
class AsyncIterator(AsyncIterable[T], Protocol):
    def __aiter__(self) -> 'AsyncIterator[T]': return self
    @abstractmethod
    def __anext__(self) -> Awaitable[T]: pass

@runtime
class Sequence(Iterable[T], Protocol):
    @abstractmethod
    def __getitem__(self, n: Any) -> T: pass

@runtime
class Mapping(Protocol[T, U]):
    def __getitem__(self, key: T) -> U: pass

@runtime
class MutableMapping(Mapping[T, U], Protocol):
    def __setitem__(self, k: T, v: U) -> None: pass

def NewType(name: str, tp: Type[T]) -> Callable[[T], T]:
    def new_type(x):
        return x
    return new_type

def runtime(cls: T) -> T:
    return cls

TYPE_CHECKING = 1
