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
builtinclass = 0
_promote = 0
NamedTuple = 0
Type = 0
no_type_check = 0
Callable = 0
ClassVar = 0
NoReturn = 0

# Type aliases.
List = 0
Dict = 0
Set = 0

T = TypeVar('T')
U = TypeVar('U')
V = TypeVar('V')
S = TypeVar('S')

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

class Awaitable(Generic[T]):
    @abstractmethod
    def __await__(self) -> Generator[Any, Any, T]: pass

class AwaitableGenerator(Generator[T, U, V], Awaitable[V], Generic[T, U, V, S]):
    pass

class AsyncIterable(Generic[T]):
    @abstractmethod
    def __aiter__(self) -> 'AsyncIterator[T]': pass

class AsyncIterator(AsyncIterable[T], Generic[T]):
    def __aiter__(self) -> 'AsyncIterator[T]': return self
    @abstractmethod
    def __anext__(self) -> Awaitable[T]: pass

class Sequence(Iterable[T], Generic[T]):
    # Use int because slice isn't defined in the default test builtins
    @abstractmethod
    def __getitem__(self, n: int) -> T: pass

class Mapping(Generic[T, U]): pass

class MutableMapping(Generic[T, U]): pass

def NewType(name: str, tp: Type[T]) -> Callable[[T], T]:
    def new_type(x: T) -> T:
        return x
    return new_type

TYPE_CHECKING = 1
