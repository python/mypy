# Stub for typing module. Many of the definitions have special handling in
# the type checker, so they can just be initialized to anything.

from abc import abstractmethod

cast = object()
overload = object()
Undefined = object()
Any = object()
Union = object()
typevar = object()
Generic = object()
AbstractGeneric = object()
Tuple = object()
Callable = object()
builtinclass = object()
ducktype = object()
disjointclass = object()
NamedTuple = object()

# Type aliases.
List = object()
Dict = object()
Set = object()

T = typevar('T')

class Iterable(AbstractGeneric[T]):
    @abstractmethod
    def __iter__(self) -> 'Iterator[T]': pass

class Iterator(Iterable[T], AbstractGeneric[T]):
    @abstractmethod
    def __next__(self) -> T: pass
