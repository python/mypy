"""Stubs for typing"""

from abc import abstractmethod, ABCMeta


# Definitions of special type checking related constructs.  Their definition
# are not used, so their value does not matter.

cast = object()
overload = object()
Undefined = object()
Any = object()
typevar = object()
Generic = object()
AbstractGeneric = object()
Tuple = object()
Function = object()

# Type aliases.
List = object()
Dict = object()
Set = object()

# Defines aliases for built-in types.
# Note that here 're' refers to the stub!  The Python 're' module does not
# define Pattern or BytesPattern.  At runtime, these actually point to the
# same type, which means that they can't be used for overloading reliably.
from re import Pattern, BytesPattern


# Abstract base classes.

T = typevar('T')
KT = typevar('KT')
VT = typevar('VT')


# TODO Container etc.

class SupportsInt(metaclass=ABCMeta):
    @abstractmethod
    def __int__(self) -> int: pass
    
class SupportsFloat(metaclass=ABCMeta):
    @abstractmethod
    def __float__(self) -> float: pass

class SupportsAbs(AbstractGeneric[T]):
    @abstractmethod
    def __abs__(self) -> T: pass

class SupportsRound(AbstractGeneric[T]):
    @abstractmethod
    def __round__(self, ndigits: int = 0) -> T: pass

class Reversible(AbstractGeneric[T]):
    @abstractmethod
    def __reversed__(self) -> Iterator[T]: pass

class Sized(metaclass=ABCMeta):
    @abstractmethod
    def __len__(self) -> int: pass

class Iterable(AbstractGeneric[T]):
    @abstractmethod
    def __iter__(self) -> Iterator[T]: pass

class Iterator(Iterable[T], AbstractGeneric[T]):
    @abstractmethod
    def __next__(self) -> T: pass

class Sequence(Sized, Iterable[T], AbstractGeneric[T]):
    @abstractmethod
    def __contains__(self, x: object) -> bool: pass
    @overload
    @abstractmethod
    def __getitem__(self, i: int) -> T: pass
    @overload
    @abstractmethod
    def __getitem__(self, s: slice) -> Sequence[T]: pass
    
class AbstractSet(Sized, Iterable[T], AbstractGeneric[T]):
    @abstractmethod
    def __contains__(self, x: object) -> bool: pass
    # TODO __le__, __lt__, __gt__, __ge__
    @abstractmethod
    def __and__(self, s: AbstractSet[T]) -> AbstractSet[T]: pass
    @abstractmethod
    def __or__(self, s: AbstractSet[T]) -> AbstractSet[T]: pass
    @abstractmethod
    def __sub__(self, s: AbstractSet[T]) -> AbstractSet[T]: pass
    @abstractmethod
    def __xor__(self, s: AbstractSet[T]) -> AbstractSet[T]: pass
    # TODO argument can be any container?
    @abstractmethod
    def isdisjoint(self, s: AbstractSet[T]) -> bool: pass

class Mapping(Sized, Iterable[KT], AbstractGeneric[KT, VT]):
    @abstractmethod
    def __getitem__(self, k: KT) -> VT: pass
    @abstractmethod
    def __setitem__(self, k: KT, v: VT) -> None: pass
    @abstractmethod
    def __delitem__(self, v: KT) -> None: pass
    @abstractmethod
    def __contains__(self, o: object) -> bool: pass

    @abstractmethod
    def clear(self) -> None: pass
    @abstractmethod
    def copy(self) -> Mapping[KT, VT]: pass
    @overload
    @abstractmethod
    def get(self, k: KT) -> VT: pass
    @overload
    @abstractmethod
    def get(self, k: KT, default: VT) -> VT: pass
    @overload
    @abstractmethod
    def pop(self, k: KT) -> VT: pass
    @overload
    @abstractmethod
    def pop(self, k: KT, default: VT) -> VT: pass
    @abstractmethod
    def popitem(self) -> Tuple[KT, VT]: pass
    @overload
    @abstractmethod
    def setdefault(self, k: KT) -> VT: pass
    @overload
    @abstractmethod
    def setdefault(self, k: KT, default: VT) -> VT: pass
    
    # TODO keyword arguments
    @overload
    @abstractmethod
    def update(self, m: Mapping[KT, VT]) -> None: pass
    @overload
    @abstractmethod
    def update(self, m: Iterable[Tuple[KT, VT]]) -> None: pass
    
    # TODO use views for the return values instead
    @abstractmethod
    def keys(self) -> AbstractSet[KT]: pass
    @abstractmethod
    def values(self) -> AbstractSet[VT]: pass
    @abstractmethod
    def items(self) -> AbstractSet[Tuple[KT, VT]]: pass

class IO(metaclass=ABCMeta):    
    # TODO iteration
    # TODO mode
    # TODO name
    # TODO detach
    # TODO readinto
    # TODO read1?
    # TODO peek?
    @abstractmethod
    def close(self) -> None: pass
    @abstractmethod
    def closed(self) -> bool: pass
    @abstractmethod
    def fileno(self) -> int: pass
    @abstractmethod
    def flush(self) -> None: pass
    @abstractmethod
    def isatty(self) -> bool: pass
    # TODO what if n is None?
    @abstractmethod
    def read(self, n: int = -1) -> bytes: pass
    @abstractmethod
    def readable(self) -> bool: pass
    @abstractmethod
    def readline(self, limit: int = -1) -> bytes: pass
    @abstractmethod
    def readlines(self, hint: int = -1) -> list[bytes]: pass
    @abstractmethod
    def seek(self, offset: int, whence: int = 0) -> int: pass
    @abstractmethod
    def seekable(self) -> bool: pass
    @abstractmethod
    def tell(self) -> int: pass
    # TODO None should not be compatible with int
    @abstractmethod
    def truncate(self, size: int = None) -> int: pass
    @abstractmethod
    def writable(self) -> bool: pass
    # TODO buffer objects
    @overload
    @abstractmethod
    def write(self, s: bytes) -> int: pass
    @overload
    @abstractmethod
    def write(self, s: bytearray) -> int: pass
    @abstractmethod
    def writelines(self, lines: list[bytes]) -> None: pass

    @abstractmethod
    def __enter__(self) -> IO: pass
    @abstractmethod
    def __exit__(self, type, value, traceback) -> None: pass

class TextIO(metaclass=ABCMeta):
    # TODO iteration
    # TODO buffer?
    # TODO str encoding
    # TODO str errors
    # TODO line_buffering
    # TODO mode
    # TODO name
    # TODO any newlines
    # TODO detach(self)
    @abstractmethod
    def close(self) -> None: pass
    @abstractmethod
    def closed(self) -> bool: pass
    @abstractmethod
    def fileno(self) -> int: pass
    @abstractmethod
    def flush(self) -> None: pass
    @abstractmethod
    def isatty(self) -> bool: pass
    # TODO what if n is None?
    @abstractmethod
    def read(self, n: int = -1) -> str: pass
    @abstractmethod
    def readable(self) -> bool: pass
    @abstractmethod
    def readline(self, limit: int = -1) -> str: pass
    @abstractmethod
    def readlines(self, hint: int = -1) -> list[str]: pass
    @abstractmethod
    def seek(self, offset: int, whence: int = 0) -> int: pass
    @abstractmethod
    def seekable(self) -> bool: pass
    @abstractmethod
    def tell(self) -> int: pass
    # TODO is None compatible with int?
    @abstractmethod
    def truncate(self, size: int = None) -> int: pass
    @abstractmethod
    def writable(self) -> bool: pass
    # TODO buffer objects
    @abstractmethod
    def write(self, s: str) -> int: pass
    @abstractmethod
    def writelines(self, lines: list[str]) -> None: pass

    @abstractmethod
    def __enter__(self) -> TextIO: pass
    @abstractmethod
    def __exit__(self, type, value, traceback) -> None: pass
