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
no_type_check = 0

# Type aliases.
List = 0
Dict = 0
Set = 0

T = TypeVar('T')

class Container(Generic[T]):
    @abstractmethod
    def __contains__(self, arg: T) -> bool: ...

class Sized:
    @abstractmethod
    def __len__(self) -> int: ...

class Iterable(Generic[T]):
    @abstractmethod
    def __iter__(self) -> 'Iterator[T]': pass

class Iterator(Iterable[T], Generic[T]):
    @abstractmethod
    def __next__(self) -> T: pass

class Sequence(Generic[T]):
    @abstractmethod
    def __getitem__(self, n: Any) -> T: pass
