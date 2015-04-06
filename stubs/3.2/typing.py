# Stubs for typing

from abc import abstractmethod, ABCMeta

# Definitions of special type checking related constructs.  Their definition
# are not used, so their value does not matter.

cast = object()
overload = object()
Undefined = object()
Any = object()
TypeVar = object()
Generic = object()
Tuple = object()
Callable = object()
builtinclass = object()
_promote = object()
NamedTuple = object()

# Type aliases and type constructors

class TypeAlias:
    # Class for defining generic aliases for library types.
    def __init__(self, target_type): pass
    def __getitem__(self, typeargs): pass

Union = TypeAlias(object)
Optional = TypeAlias(object)
List = TypeAlias(object)
Dict = TypeAlias(object)
Set = TypeAlias(object)

# Predefined type variables.
AnyStr = TypeVar('AnyStr', str, bytes)

# Abstract base classes.

_T = TypeVar('_T')
_KT = TypeVar('_KT')
_VT = TypeVar('_VT')

# TODO Container etc.

class SupportsInt(metaclass=ABCMeta):
    @abstractmethod
    def __int__(self) -> int: pass

class SupportsFloat(metaclass=ABCMeta):
    @abstractmethod
    def __float__(self) -> float: pass

class SupportsAbs(Generic[_T]):
    @abstractmethod
    def __abs__(self) -> _T: pass

class SupportsRound(Generic[_T]):
    @abstractmethod
    def __round__(self, ndigits: int = 0) -> _T: pass

class Reversible(Generic[_T]):
    @abstractmethod
    def __reversed__(self) -> Iterator[_T]: pass

class Sized(metaclass=ABCMeta):
    @abstractmethod
    def __len__(self) -> int: pass

class Hashable(metaclass=ABCMeta):
    # TODO: This is special, in that a subclass of a hashable class may not be hashable
    #   (for example, list vs. object). It's not obvious how to represent this. This class
    #   is currently mostly useless for static checking.
    @abstractmethod
    def __hash__(self) -> int: pass

class Iterable(Generic[_T]):
    @abstractmethod
    def __iter__(self) -> Iterator[_T]: pass

class Iterator(Iterable[_T], Generic[_T]):
    @abstractmethod
    def __next__(self) -> _T: pass
    def __iter__(self) -> Iterator[_T]: pass

class Container(Generic[_T]):
    @abstractmethod
    def __contains__(self, x: object) -> bool: pass

class Sequence(Iterable[_T], Container[_T], Sized, Reversible[_T], Generic[_T]):
    @overload
    @abstractmethod
    def __getitem__(self, i: int) -> _T: pass
    @overload
    @abstractmethod
    def __getitem__(self, s: slice) -> Sequence[_T]: pass
    # Mixin methods
    def index(self, x: Any) -> int: pass
    def count(self, x: Any) -> int: pass
    def __contains__(self, x: object) -> bool: pass
    def __iter__(self) -> Iterator[_T]: pass
    def __reversed__(self) -> Iterator[_T]: pass

class MutableSequence(Sequence[_T], Generic[_T]):
    @abstractmethod
    def insert(self, index: int, object: _T) -> None: pass
    @overload
    @abstractmethod
    def __setitem__(self, i: int, o: _T) -> None: pass
    @overload
    @abstractmethod
    def __setitem__(self, s: slice, o: Sequence[_T]) -> None: pass
    @abstractmethod
    def __delitem__(self, i: Union[int, slice]) -> None: pass
    # Mixin methods
    def append(self, object: _T) -> None: pass
    def extend(self, iterable: Iterable[_T]) -> None: pass
    def reverse(self) -> None: pass
    def pop(self, index: int = -1) -> _T: pass
    def remove(self, object: _T) -> None: pass
    def __iadd__(self, x: Iterable[_T]) -> MutableSequence[_T]: pass

class AbstractSet(Iterable[_T], Container[_T], Sized, Generic[_T]):
    @abstractmethod
    def __contains__(self, x: object) -> bool: pass
    # Mixin methods
    def __le__(self, s: AbstractSet[Any]) -> bool: pass
    def __lt__(self, s: AbstractSet[Any]) -> bool: pass
    def __gt__(self, s: AbstractSet[Any]) -> bool: pass
    def __ge__(self, s: AbstractSet[Any]) -> bool: pass
    def __and__(self, s: AbstractSet[Any]) -> AbstractSet[_T]: pass
    # In order to support covariance, _T should not be used within an argument
    # type. We need union types to properly model this.
    def __or__(self, s: AbstractSet[_T]) -> AbstractSet[_T]: pass
    def __sub__(self, s: AbstractSet[Any]) -> AbstractSet[_T]: pass
    def __xor__(self, s: AbstractSet[_T]) -> AbstractSet[_T]: pass
    # TODO: Argument can be a more general ABC?
    def isdisjoint(self, s: AbstractSet[Any]) -> bool: pass

class MutableSet(AbstractSet[_T], Generic[_T]):
    @abstractmethod
    def add(self, x: _T) -> None: pass
    @abstractmethod
    def discard(self, x: _T) -> None: pass
    # Mixin methods
    def clear(self) -> None: pass
    def pop(self) -> _T: pass
    def remove(self, element: _T) -> None: pass
    def __ior__(self, s: AbstractSet[_T]) -> MutableSet[_T]: pass
    def __iand__(self, s: AbstractSet[Any]) -> MutableSet[_T]: pass
    def __ixor__(self, s: AbstractSet[_T]) -> MutableSet[_T]: pass
    def __isub__(self, s: AbstractSet[Any]) -> MutableSet[_T]: pass

class MappingView(Sized):
    def __len__(self) -> int: pass

class ItemsView(AbstractSet[Tuple[_KT, _VT]], MappingView, Generic[_KT, _VT]):
    def __contains__(self, o: object) -> bool: pass
    def __iter__(self) -> Iterator[Tuple[_KT, _VT]]: pass

class KeysView(AbstractSet[_T], MappingView, Generic[_T]):
    def __contains__(self, o: object) -> bool: pass
    def __iter__(self) -> Iterator[_T]: pass

class ValuesView(MappingView, Iterable[_T], Generic[_T]):
    def __contains__(self, o: object) -> bool: pass
    def __iter__(self) -> Iterator[_T]: pass

class Mapping(Iterable[_KT], Container[_KT], Sized, Generic[_KT, _VT]):
    @abstractmethod
    def __getitem__(self, k: _KT) -> _VT: pass
    # Mixin methods
    def get(self, k: _KT, default: _VT = Undefined) -> _VT: pass
    def items(self) -> AbstractSet[Tuple[_KT, _VT]]: pass
    def keys(self) -> AbstractSet[_KT]: pass
    def values(self) -> ValuesView[_VT]: pass
    def __contains__(self, o: object) -> bool: pass

class MutableMapping(Mapping[_KT, _VT], Generic[_KT, _VT]):
    @abstractmethod
    def __setitem__(self, k: _KT, v: _VT) -> None: pass
    @abstractmethod
    def __delitem__(self, v: _KT) -> None: pass

    def clear(self) -> None: pass
    def pop(self, k: _KT, default: _VT = Undefined) -> _VT: pass
    def popitem(self) -> Tuple[_KT, _VT]: pass
    def setdefault(self, k: _KT, default: _VT = Undefined) -> _VT: pass
    def update(self, m: Union[Mapping[_KT, _VT],
                              Iterable[Tuple[_KT, _VT]]]) -> None: pass

class IO(Iterable[AnyStr], Generic[AnyStr]):
    # TODO detach
    # TODO use abstract properties
    @property
    def mode(self) -> str: pass
    @property
    def name(self) -> str: pass
    @abstractmethod
    def close(self) -> None: pass
    @property
    def closed(self) -> bool: pass
    @abstractmethod
    def fileno(self) -> int: pass
    @abstractmethod
    def flush(self) -> None: pass
    @abstractmethod
    def isatty(self) -> bool: pass
    # TODO what if n is None?
    @abstractmethod
    def read(self, n: int = -1) -> AnyStr: pass
    @abstractmethod
    def readable(self) -> bool: pass
    @abstractmethod
    def readline(self, limit: int = -1) -> AnyStr: pass
    @abstractmethod
    def readlines(self, hint: int = -1) -> list[AnyStr]: pass
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
    @abstractmethod
    def write(self, s: AnyStr) -> int: pass
    @abstractmethod
    def writelines(self, lines: Iterable[AnyStr]) -> None: pass

    @abstractmethod
    def __iter__(self) -> Iterator[AnyStr]: pass
    @abstractmethod
    def __enter__(self) -> 'IO[AnyStr]': pass
    @abstractmethod
    def __exit__(self, type, value, traceback) -> bool: pass

class BinaryIO(IO[bytes]):
    # TODO readinto
    # TODO read1?
    # TODO peek?
    @overload
    @abstractmethod
    def write(self, s: bytes) -> int: pass
    @overload
    @abstractmethod
    def write(self, s: bytearray) -> int: pass

    @abstractmethod
    def __enter__(self) -> BinaryIO: pass

class TextIO(IO[str]):
    # TODO use abstractproperty
    @property
    def buffer(self) -> BinaryIO: pass
    @property
    def encoding(self) -> str: pass
    @property
    def errors(self) -> str: pass
    @property
    def line_buffering(self) -> int: pass  # int on PyPy, bool on CPython
    @property
    def newlines(self) -> Any: pass # None, str or tuple
    @abstractmethod
    def __enter__(self) -> TextIO: pass

class ByteString(Sequence[int]): pass

class Match(Generic[AnyStr]):
    pos = 0
    endpos = 0
    lastindex = 0
    lastgroup = Undefined(AnyStr)
    string = Undefined(AnyStr)

    # The regular expression object whose match() or search() method produced
    # this match instance.
    re = Undefined('Pattern[AnyStr]')

    def expand(self, template: AnyStr) -> AnyStr: pass

    @overload
    def group(self, group1: int = 0) -> AnyStr: pass
    @overload
    def group(self, group1: str) -> AnyStr: pass
    @overload
    def group(self, group1: int, group2: int,
              *groups: int) -> Sequence[AnyStr]: pass
    @overload
    def group(self, group1: str, group2: str,
              *groups: str) -> Sequence[AnyStr]: pass

    def groups(self, default: AnyStr = None) -> Sequence[AnyStr]: pass
    def groupdict(self, default: AnyStr = None) -> dict[str, AnyStr]: pass
    def start(self, group: int = 0) -> int: pass
    def end(self, group: int = 0) -> int: pass
    def span(self, group: int = 0) -> Tuple[int, int]: pass

class Pattern(Generic[AnyStr]):
    flags = 0
    groupindex = 0
    groups = 0
    pattern = Undefined(AnyStr)

    def search(self, string: AnyStr, pos: int = 0,
               endpos: int = -1) -> Match[AnyStr]: pass
    def match(self, string: AnyStr, pos: int = 0,
              endpos: int = -1) -> Match[AnyStr]: pass
    def split(self, string: AnyStr, maxsplit: int = 0) -> list[AnyStr]: pass
    def findall(self, string: AnyStr, pos: int = 0,
                endpos: int = -1) -> list[AnyStr]: pass
    def finditer(self, string: AnyStr, pos: int = 0,
                 endpos: int = -1) -> Iterator[Match[AnyStr]]: pass

    @overload
    def sub(self, repl: AnyStr, string: AnyStr,
            count: int = 0) -> AnyStr: pass
    @overload
    def sub(self, repl: Callable[[Match[AnyStr]], AnyStr], string: AnyStr,
            count: int = 0) -> AnyStr: pass

    @overload
    def subn(self, repl: AnyStr, string: AnyStr,
             count: int = 0) -> Tuple[AnyStr, int]: pass
    @overload
    def subn(self, repl: Callable[[Match[AnyStr]], AnyStr], string: AnyStr,
             count: int = 0) -> Tuple[AnyStr, int]: pass
