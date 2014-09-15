# Stubs for typing (Python 2.7)

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
builtinclass = object()
ducktype = object()
disjointclass = object()

# Type aliases

class TypeAlias:
    """Class for defining generic aliases for library types."""

    def __init__(self, target_type):
        self.target_type = target_type

    def __getitem__(self, typeargs):
        return self.target_type

Union = TypeAlias(object)
List = TypeAlias(object)
Dict = TypeAlias(object)
Set = TypeAlias(object)

# Predefined type variables.
AnyStr = typevar('AnyStr', values=(str, unicode))

# Abstract base classes.

_T = typevar('_T')
_KT = typevar('_KT')
_VT = typevar('_VT')

# TODO Container etc.

class SupportsInt(metaclass=ABCMeta):
    @abstractmethod
    def __int__(self) -> int: pass

class SupportsFloat(metaclass=ABCMeta):
    @abstractmethod
    def __float__(self) -> float: pass

class SupportsAbs(AbstractGeneric[_T]):
    @abstractmethod
    def __abs__(self) -> _T: pass

@disjointclass(int)
@disjointclass(float)
class SupportsRound(AbstractGeneric[_T]):
    @abstractmethod
    def __round__(self, ndigits: int = 0) -> _T: pass

class Reversible(AbstractGeneric[_T]):
    @abstractmethod
    def __reversed__(self) -> Iterator[_T]: pass

class Sized(metaclass=ABCMeta):
    @abstractmethod
    def __len__(self) -> int: pass

class Iterable(AbstractGeneric[_T]):
    @abstractmethod
    def __iter__(self) -> Iterator[_T]: pass

class Iterator(Iterable[_T], AbstractGeneric[_T]):
    @abstractmethod
    def next(self) -> _T: pass

class Sequence(Sized, Iterable[_T], AbstractGeneric[_T]):
    @abstractmethod
    def __contains__(self, x: object) -> bool: pass
    @overload
    @abstractmethod
    def __getitem__(self, i: int) -> _T: pass
    @overload
    @abstractmethod
    def __getitem__(self, s: slice) -> Sequence[_T]: pass

class AbstractSet(Sized, Iterable[_T], AbstractGeneric[_T]):
    @abstractmethod
    def __contains__(self, x: object) -> bool: pass
    # TODO __le__, __lt__, __gt__, __ge__
    @abstractmethod
    def __and__(self, s: AbstractSet[_T]) -> AbstractSet[_T]: pass
    @abstractmethod
    def __or__(self, s: AbstractSet[_T]) -> AbstractSet[_T]: pass
    @abstractmethod
    def __sub__(self, s: AbstractSet[_T]) -> AbstractSet[_T]: pass
    @abstractmethod
    def __xor__(self, s: AbstractSet[_T]) -> AbstractSet[_T]: pass
    # TODO argument can be any container?
    @abstractmethod
    def isdisjoint(self, s: AbstractSet[_T]) -> bool: pass

class Mapping(Sized, Iterable[_KT], AbstractGeneric[_KT, _VT]):
    @abstractmethod
    def __getitem__(self, k: _KT) -> _VT: pass
    @abstractmethod
    def __setitem__(self, k: _KT, v: _VT) -> None: pass
    @abstractmethod
    def __delitem__(self, v: _KT) -> None: pass
    @abstractmethod
    def __contains__(self, o: object) -> bool: pass

    @abstractmethod
    def clear(self) -> None: pass
    @abstractmethod
    def copy(self) -> Mapping[_KT, _VT]: pass
    @overload
    @abstractmethod
    def get(self, k: _KT) -> _VT: pass
    @overload
    @abstractmethod
    def get(self, k: _KT, default: _VT) -> _VT: pass
    @overload
    @abstractmethod
    def pop(self, k: _KT) -> _VT: pass
    @overload
    @abstractmethod
    def pop(self, k: _KT, default: _VT) -> _VT: pass
    @abstractmethod
    def popitem(self) -> Tuple[_KT, _VT]: pass
    @overload
    @abstractmethod
    def setdefault(self, k: _KT) -> _VT: pass
    @overload
    @abstractmethod
    def setdefault(self, k: _KT, default: _VT) -> _VT: pass

    # TODO keyword arguments
    @overload
    @abstractmethod
    def update(self, m: Mapping[_KT, _VT]) -> None: pass
    @overload
    @abstractmethod
    def update(self, m: Iterable[Tuple[_KT, _VT]]) -> None: pass

    @abstractmethod
    def keys(self) -> list[_KT]: pass
    @abstractmethod
    def values(self) -> list[_VT]: pass
    @abstractmethod
    def items(self) -> list[Tuple[_KT, _VT]]: pass
    @abstractmethod
    def iterkeys(self) -> Iterator[_KT]: pass
    @abstractmethod
    def itervalues(self) -> Iterator[_VT]: pass
    @abstractmethod
    def iteritems(self) -> Iterator[Tuple[_KT, _VT]]: pass

class IO(Iterable[AnyStr], AbstractGeneric[AnyStr]):
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

class BinaryIO(IO[str]):
    # TODO readinto
    # TODO read1?
    # TODO peek?
    @overload
    @abstractmethod
    def write(self, s: str) -> int: pass
    @overload
    @abstractmethod
    def write(self, s: bytearray) -> int: pass

    @abstractmethod
    def __enter__(self) -> BinaryIO: pass

class TextIO(IO[unicode]):
    # TODO use abstractproperty
    @property
    def buffer(self) -> BinaryIO: pass
    @property
    def encoding(self) -> str: pass
    @property
    def errors(self) -> str: pass
    @property
    def line_buffering(self) -> bool: pass
    @property
    def newlines(self) -> Any: pass # None, str or tuple
    @abstractmethod
    def __enter__(self) -> TextIO: pass

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
    def sub(self, repl: Function[[Match[AnyStr]], AnyStr], string: AnyStr,
            count: int = 0) -> AnyStr: pass

    @overload
    def subn(self, repl: AnyStr, string: AnyStr,
             count: int = 0) -> Tuple[AnyStr, int]: pass
    @overload
    def subn(self, repl: Function[[Match[AnyStr]], AnyStr], string: AnyStr,
             count: int = 0) -> Tuple[AnyStr, int]: pass
