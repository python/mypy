# Test stub for typing module, with features for async/await related tests.
#
# Use [typing fixtures/typing-async.pyi] to use this instead of lib-stub/typing.pyi
# in a particular test case.
#
# Many of the definitions have special handling in the type checker, so they
# can just be initialized to anything.

from abc import abstractmethod, ABCMeta

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
NamedTuple = 0
Type = 0
ClassVar = 0
Final = 0
Literal = 0
NoReturn = 0
Self = 0

T = TypeVar('T')
T_co = TypeVar('T_co', covariant=True)
T_contra = TypeVar('T_contra', contravariant=True)
U = TypeVar('U')
V = TypeVar('V')
S = TypeVar('S')

# Note: definitions below are different from typeshed, variances are declared
# to silence the protocol variance checks. Maybe it is better to use type: ignore?

class Container(Protocol[T_co]):
    @abstractmethod
    # Use int because bool isn't in the default test builtins
    def __contains__(self, arg: object) -> int: pass

class Iterable(Protocol[T_co]):
    @abstractmethod
    def __iter__(self) -> 'Iterator[T_co]': pass

class Iterator(Iterable[T_co], Protocol):
    @abstractmethod
    def __next__(self) -> T_co: pass

class Generator(Iterator[T], Generic[T, U, V]):
    @abstractmethod
    def send(self, value: U) -> T: pass

    @abstractmethod
    def throw(self, typ: Any, val: Any=None, tb: Any=None) -> None: pass

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

class Awaitable(Protocol[T]):
    @abstractmethod
    def __await__(self) -> Generator[Any, Any, T]: pass

class AwaitableGenerator(Generator[T, U, V], Awaitable[V], Generic[T, U, V, S], metaclass=ABCMeta):
    pass

class Coroutine(Awaitable[V], Generic[T, U, V]):
    @abstractmethod
    def send(self, value: U) -> T: pass

    @abstractmethod
    def throw(self, typ: Any, val: Any=None, tb: Any=None) -> None: pass

    @abstractmethod
    def close(self) -> None: pass

class AsyncIterable(Protocol[T]):
    @abstractmethod
    def __aiter__(self) -> 'AsyncIterator[T]': pass

class AsyncIterator(AsyncIterable[T], Protocol):
    def __aiter__(self) -> 'AsyncIterator[T]': return self
    @abstractmethod
    def __anext__(self) -> Awaitable[T]: pass

class Sequence(Iterable[T_co], Container[T_co]):
    @abstractmethod
    def __getitem__(self, n: Any) -> T_co: pass

class Mapping(Iterable[T], Generic[T, T_co], metaclass=ABCMeta):
    def keys(self) -> Iterable[T]: pass  # Approximate return type
    def __getitem__(self, key: T) -> T_co: pass
    @overload
    def get(self, k: T) -> Optional[T_co]: pass
    @overload
    def get(self, k: T, default: Union[T_co, V]) -> Union[T_co, V]: pass

class ContextManager(Generic[T]):
    def __enter__(self) -> T: pass
    # Use Any because not all the precise types are in the fixtures.
    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> Any: pass

class AsyncContextManager(Generic[T]):
    def __aenter__(self) -> Awaitable[T]: pass
    # Use Any because not all the precise types are in the fixtures.
    def __aexit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> Awaitable[Any]: pass

class _SpecialForm: pass
