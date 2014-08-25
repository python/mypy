# Stubs for builtins (Python 2.7)

from typing import (
    Undefined, typevar, AbstractGeneric, Iterator, Iterable, overload,
    Sequence, Mapping, Tuple, List, Any, Dict, Function, Generic, Set,
    AbstractSet, Sized, Reversible, SupportsInt, SupportsFloat, SupportsAbs,
    SupportsRound, IO, BinaryIO, builtinclass, ducktype
)
from abc import abstractmethod, ABCMeta

_T = typevar('_T')
_KT = typevar('_KT')
_VT = typevar('_VT')
_S = typevar('_S')
_T1 = typevar('_T1')
_T2 = typevar('_T2')
_T3 = typevar('_T3')
_T4 = typevar('_T4')

staticmethod = object() # Only valid as a decorator.
classmethod = object() # Only valid as a decorator.
property = object()

@builtinclass
class object:
    __doc__ = ''
    __class__ = Undefined # type: type

    def __init__(self) -> None: pass
    def __eq__(self, o: object) -> bool: pass
    def __ne__(self, o: object) -> bool: pass
    def __str__(self) -> str: pass
    def __repr__(self) -> str: pass
    def __hash__(self) -> int: pass

@builtinclass
class type:
    __name__ = ''
    __module__ = ''
    __dict__ = Undefined # type: Dict[unicode, Any]

    def __init__(self, o: object) -> None: pass

@builtinclass
@ducktype(float)
class int(SupportsInt, SupportsFloat, SupportsAbs[int]):
    @overload
    def __init__(self) -> None: pass
    @overload
    def __init__(self, x: SupportsInt) -> None: pass
    @overload
    def __init__(self, x: unicode, base: int = 10) -> None: pass
    @overload
    def __init__(self, x: bytearray, base: int = 10) -> None: pass
    def bit_length(self) -> int: pass

    def __add__(self, x: int) -> int: pass
    def __sub__(self, x: int) -> int: pass
    def __mul__(self, x: int) -> int: pass
    def __floordiv__(self, x: int) -> int: pass
    def __div__(self, x: int) -> int: pass
    def __truediv__(self, x: int) -> float: pass
    def __mod__(self, x: int) -> int: pass
    def __radd__(self, x: int) -> int: pass
    def __rsub__(self, x: int) -> int: pass
    def __rmul__(self, x: int) -> int: pass
    def __rfloordiv__(self, x: int) -> int: pass
    def __rdiv__(self, x: int) -> int: pass
    def __rtruediv__(self, x: int) -> float: pass
    def __rmod__(self, x: int) -> int: pass
    def __pow__(self, x: int) -> Any: pass  # Return type can be int or float, depending on x.
    def __rpow__(self, x: int) -> Any: pass
    def __and__(self, n: int) -> int: pass
    def __or__(self, n: int) -> int: pass
    def __xor__(self, n: int) -> int: pass
    def __lshift__(self, n: int) -> int: pass
    def __rshift__(self, n: int) -> int: pass
    def __rand__(self, n: int) -> int: pass
    def __ror__(self, n: int) -> int: pass
    def __rxor__(self, n: int) -> int: pass
    def __rlshift__(self, n: int) -> int: pass
    def __rrshift__(self, n: int) -> int: pass
    def __neg__(self) -> int: pass
    def __pos__(self) -> int: pass
    def __invert__(self) -> int: pass

    def __eq__(self, x: object) -> bool: pass
    def __ne__(self, x: object) -> bool: pass
    def __lt__(self, x: int) -> bool: pass
    def __le__(self, x: int) -> bool: pass
    def __gt__(self, x: int) -> bool: pass
    def __ge__(self, x: int) -> bool: pass

    def __str__(self) -> str: pass
    def __float__(self) -> float: pass
    def __int__(self) -> int: return self
    def __abs__(self) -> int: pass
    def __hash__(self) -> int: pass

@builtinclass
class float(SupportsFloat, SupportsInt, SupportsAbs[float]):
    @overload
    def __init__(self) -> None: pass
    @overload
    def __init__(self, x: SupportsFloat) -> None: pass
    @overload
    def __init__(self, x: unicode) -> None: pass
    @overload
    def __init__(self, x: bytearray) -> None: pass

    def __add__(self, x: float) -> float: pass
    def __sub__(self, x: float) -> float: pass
    def __mul__(self, x: float) -> float: pass
    def __floordiv__(self, x: float) -> float: pass
    def __div__(self, x: float) -> float: pass
    def __truediv__(self, x: float) -> float: pass
    def __mod__(self, x: float) -> float: pass
    def __pow__(self, x: float) -> float: pass
    def __radd__(self, x: float) -> float: pass
    def __rsub__(self, x: float) -> float: pass
    def __rmul__(self, x: float) -> float: pass
    def __rfloordiv__(self, x: float) -> float: pass
    def __rdiv__(self, x: float) -> float: pass
    def __rtruediv__(self, x: float) -> float: pass
    def __rmod__(self, x: float) -> float: pass
    def __rpow__(self, x: float) -> float: pass

    def __eq__(self, x: object) -> bool: pass
    def __ne__(self, x: object) -> bool: pass
    def __lt__(self, x: float) -> bool: pass
    def __le__(self, x: float) -> bool: pass
    def __gt__(self, x: float) -> bool: pass
    def __ge__(self, x: float) -> bool: pass
    def __neg__(self) -> float: pass
    def __pos__(self) -> float: pass

    def __str__(self) -> str: pass
    def __int__(self) -> int: pass
    def __float__(self) -> float: return self
    def __abs__(self) -> float: pass
    def __hash__(self) -> int: pass

@builtinclass
class complex:
    def __init__(self, re: float, im: float = 0.0) -> None: pass
    # TODO this is just a placeholder; add more members

@builtinclass
class unicode(Sequence[unicode]):
    @overload
    def __init__(self) -> None: pass
    @overload
    def __init__(self, o: object) -> None: pass
    @overload
    def __init__(self, o: str, encoding: unicode = None, errors: unicode = 'strict') -> None: pass
    @overload
    def __init__(self, o: bytearray, encoding: unicode = None,
                 errors: unicode = 'strict') -> None: pass
    def capitalize(self) -> unicode: pass
    def center(self, width: int, fillchar: unicode = u' ') -> unicode: pass
    def count(self, x: unicode) -> int: pass
    def decode(self, encoding: unicode = 'utf-8', errors: unicode = 'strict') -> unicode: pass
    def encode(self, encoding: unicode = 'utf-8', errors: unicode = 'strict') -> str: pass
    def endswith(self, suffix: unicode, start: int = 0,
                 end: int = None) -> bool: pass  # TODO tuple suffix; None value for int
    def expandtabs(self, tabsize: int = 8) -> unicode: pass
    def find(self, sub: unicode, start: int = 0, end: int = 0) -> int: pass
    def format(self, *args: Any, **kwargs: Any) -> unicode: pass
    def format_map(self, map: Mapping[unicode, Any]) -> unicode: pass
    def index(self, sub: unicode, start: int = 0, end: int = 0) -> int: pass
    def isalnum(self) -> bool: pass
    def isalpha(self) -> bool: pass
    def isdecimal(self) -> bool: pass
    def isdigit(self) -> bool: pass
    def isidentifier(self) -> bool: pass
    def islower(self) -> bool: pass
    def isnumeric(self) -> bool: pass
    def isprintable(self) -> bool: pass
    def isspace(self) -> bool: pass
    def istitle(self) -> bool: pass
    def isupper(self) -> bool: pass
    def join(self, iterable: Iterable[unicode]) -> unicode: pass
    def ljust(self, width: int, fillchar: unicode = u' ') -> unicode: pass
    def lower(self) -> unicode: pass
    def lstrip(self, chars: unicode = None) -> unicode: pass
    def partition(self, sep: unicode) -> Tuple[unicode, unicode, unicode]: pass
    def replace(self, old: unicode, new: unicode, count: int = -1) -> unicode: pass
    def rfind(self, sub: unicode, start: int = 0, end: int = 0) -> int: pass
    def rindex(self, sub: unicode, start: int = 0, end: int = 0) -> int: pass
    def rjust(self, width: int, fillchar: unicode = u' ') -> unicode: pass
    def rpartition(self, sep: unicode) -> Tuple[unicode, unicode, unicode]: pass
    def rsplit(self, sep: unicode = None, maxsplit: int = -1) -> List[unicode]: pass
    def rstrip(self, chars: unicode = None) -> unicode: pass
    def split(self, sep: unicode = None, maxsplit: int = -1) -> List[unicode]: pass
    def splitlines(self, keepends: bool = False) -> List[unicode]: pass
    def startswith(self, prefix: unicode, start: int = 0,
                   end: int = None) -> bool: pass  # TODO tuple prefix; None value for int
    def strip(self, chars: unicode = None) -> unicode: pass
    def swapcase(self) -> unicode: pass
    def title(self) -> unicode: pass
    def translate(self, table: Dict[int, Any]) -> unicode: pass
    def upper(self) -> unicode: pass
    def zfill(self, width: int) -> unicode: pass
    # TODO maketrans

    @overload
    def __getitem__(self, i: int) -> unicode: pass
    @overload
    def __getitem__(self, s: slice) -> unicode: pass
    def __getslice__(self, start: int, stop: int) -> unicode: pass
    def __add__(self, s: unicode) -> unicode: pass
    def __mul__(self, n: int) -> unicode: pass
    def __mod__(self, *args: Any) -> unicode: pass
    def __eq__(self, x: object) -> bool: pass
    def __ne__(self, x: object) -> bool: pass
    def __lt__(self, x: unicode) -> bool: pass
    def __le__(self, x: unicode) -> bool: pass
    def __gt__(self, x: unicode) -> bool: pass
    def __ge__(self, x: unicode) -> bool: pass

    def __len__(self) -> int: pass
    def __contains__(self, s: object) -> bool: pass
    def __iter__(self) -> Iterator[unicode]: pass
    def __str__(self) -> str: pass
    def __repr__(self) -> str: pass
    def __int__(self) -> int: pass
    def __float__(self) -> float: pass
    def __hash__(self) -> int: pass

@builtinclass
@ducktype(unicode)
class str(Sequence[str]):
    def __init__(self, object: object) -> None: pass
    def capitalize(self) -> str: pass
    @overload
    def center(self, width: int, fillchar: str = None) -> str: pass
    @overload
    def center(self, width: int, fillchar: bytearray = None) -> str: pass
    @overload
    def count(self, x: unicode) -> int: pass
    @overload
    def count(self, x: bytearray) -> int: pass
    def decode(self, encoding: unicode = 'utf-8', errors: unicode = 'strict') -> unicode: pass
    def encode(self, encoding: unicode = 'utf-8', errors: unicode = 'strict') -> str: pass
    @overload
    def endswith(self, suffix: unicode) -> bool: pass
    @overload
    def endswith(self, suffix: bytearray) -> bool: pass
    def expandtabs(self, tabsize: int = 8) -> str: pass
    @overload
    def find(self, sub: unicode, start: int = 0) -> int: pass
    @overload
    def find(self, sub: unicode, start: int, end: int) -> int: pass
    @overload
    def find(self, sub: bytearray, start: int = 0) -> int: pass
    @overload
    def find(self, sub: bytearray, start: int, end: int) -> int: pass
    @overload
    def index(self, sub: unicode, start: int = 0) -> int: pass
    @overload
    def index(self, sub: unicode, start: int, end: int) -> int: pass
    @overload
    def index(self, sub: bytearray, start: int = 0) -> int: pass
    @overload
    def index(self, sub: bytearray, start: int, end: int) -> int: pass
    def isalnum(self) -> bool: pass
    def isalpha(self) -> bool: pass
    def isdigit(self) -> bool: pass
    def islower(self) -> bool: pass
    def isspace(self) -> bool: pass
    def istitle(self) -> bool: pass
    def isupper(self) -> bool: pass
    @overload
    def join(self, iterable: Iterable[str]) -> str: pass  # TODO unicode
    @overload
    def join(self, iterable: Iterable[bytearray]) -> str: pass
    @overload
    def ljust(self, width: int, fillchar: str = None) -> str: pass
    @overload
    def ljust(self, width: int, fillchar: bytearray = None) -> str: pass
    def lower(self) -> str: pass
    @overload
    def lstrip(self, chars: str = None) -> str: pass   # TODO unicode
    @overload
    def lstrip(self, chars: bytearray = None) -> str: pass
    @overload
    def partition(self, sep: str) -> Tuple[str, str, str]: pass   # TODO unicode
    @overload
    def partition(self, sep: bytearray) -> Tuple[str, str, str]: pass
    @overload
    def replace(self, old: str, new: str, count: int = -1) -> str: pass   # TODO unicode
    @overload
    def replace(self, old: bytearray, new: bytearray, count: int = -1) -> str: pass
    @overload
    def rfind(self, sub: unicode, start: int = 0) -> int: pass
    @overload
    def rfind(self, sub: unicode, start: int, end: int) -> int: pass
    @overload
    def rfind(self, sub: bytearray, start: int = 0) -> int: pass
    @overload
    def rfind(self, sub: bytearray, start: int, end: int) -> int: pass
    @overload
    def rindex(self, sub: unicode, start: int = 0) -> int: pass
    @overload
    def rindex(self, sub: unicode, start: int, end: int) -> int: pass
    @overload
    def rindex(self, sub: bytearray, start: int = 0) -> int: pass
    @overload
    def rindex(self, sub: bytearray, start: int, end: int) -> int: pass
    @overload
    def rjust(self, width: int, fillchar: str = None) -> str: pass
    @overload
    def rjust(self, width: int, fillchar: bytearray = None) -> str: pass
    @overload
    def rpartition(self, sep: str) -> Tuple[str, str, str]: pass  # TODO unicode
    @overload
    def rpartition(self, sep: bytearray) -> Tuple[str, str, str]: pass
    @overload
    def rsplit(self, sep: str = None,   # TODO unicode
               maxsplit: int = -1) -> List[str]: pass
    @overload
    def rsplit(self, sep: bytearray = None,
               maxsplit: int = -1) -> List[str]: pass
    @overload
    def rstrip(self, chars: str = None) -> str: pass    # TODO unicode
    @overload
    def rstrip(self, chars: bytearray = None) -> str: pass
    @overload
    def split(self, sep: str = None, maxsplit: int = -1) -> List[str]: pass   # TODO unicode
    @overload
    def split(self, sep: bytearray = None,     # TODO unicode
              maxsplit: int = -1) -> List[str]: pass
    def splitlines(self, keepends: bool = False) -> List[str]: pass
    @overload
    def startswith(self, prefix: unicode) -> bool: pass
    @overload
    def startswith(self, prefix: bytearray) -> bool: pass
    @overload
    def strip(self, chars: str = None) -> str: pass   # TODO unicode
    @overload
    def strip(self, chars: bytearray = None) -> str: pass
    def swapcase(self) -> str: pass
    def title(self) -> str: pass
    @overload
    def translate(self, table: str) -> str: pass   # TODO unicode
    @overload
    def translate(self, table: bytearray) -> str: pass
    def upper(self) -> str: pass
    def zfill(self, width: int) -> str: pass
    # TODO fromhex
    # TODO maketrans

    def __len__(self) -> int: pass
    def __iter__(self) -> Iterator[str]: pass
    def __str__(self) -> str: pass
    def __repr__(self) -> str: pass
    def __int__(self) -> int: pass
    def __float__(self) -> float: pass
    def __hash__(self) -> int: pass
    @overload
    def __getitem__(self, i: int) -> str: pass
    @overload
    def __getitem__(self, s: slice) -> str: pass
    def __getslice__(self, start: int, stop: int) -> str: pass
    @overload
    def __add__(self, s: str) -> str: pass    # TODO unicode
    @overload
    def __add__(self, s: bytearray) -> str: pass
    def __mul__(self, n: int) -> str: pass
    def __rmul__(self, n: int) -> str: pass
    def __contains__(self, o: object) -> bool: pass
    def __eq__(self, x: object) -> bool: pass
    def __ne__(self, x: object) -> bool: pass
    def __lt__(self, x: unicode) -> bool: pass
    def __le__(self, x: unicode) -> bool: pass
    def __gt__(self, x: unicode) -> bool: pass
    def __ge__(self, x: unicode) -> bool: pass


@builtinclass
class bytearray(Sequence[int]):
    @overload
    def __init__(self, ints: Iterable[int]) -> None: pass
    @overload
    def __init__(self, string: unicode, encoding: unicode,
                 errors: unicode = 'strict') -> None: pass
    @overload
    def __init__(self, length: int) -> None: pass
    @overload
    def __init__(self) -> None: pass
    def capitalize(self) -> bytearray: pass
    @overload
    def center(self, width: int, fillchar: str = None) -> bytearray: pass
    @overload
    def center(self, width: int, fillchar: bytearray = None) -> bytearray: pass
    @overload
    def count(self, x: str) -> int: pass
    @overload
    def count(self, x: bytearray) -> int: pass
    def decode(self, encoding: unicode = 'utf-8', errors: unicode = 'strict') -> str: pass
    @overload
    def endswith(self, suffix: str) -> bool: pass
    @overload
    def endswith(self, suffix: bytearray) -> bool: pass
    def expandtabs(self, tabsize: int = 8) -> bytearray: pass
    @overload
    def find(self, sub: str, start: int = 0) -> int: pass
    @overload
    def find(self, sub: str, start: int, end: int) -> int: pass
    @overload
    def find(self, sub: bytearray, start: int = 0) -> int: pass
    @overload
    def find(self, sub: bytearray, start: int, end: int) -> int: pass
    @overload
    def index(self, sub: str, start: int = 0) -> int: pass
    @overload
    def index(self, sub: str, start: int, end: int) -> int: pass
    @overload
    def index(self, sub: bytearray, start: int = 0) -> int: pass
    @overload
    def index(self, sub: bytearray, start: int, end: int) -> int: pass
    def isalnum(self) -> bool: pass
    def isalpha(self) -> bool: pass
    def isdigit(self) -> bool: pass
    def islower(self) -> bool: pass
    def isspace(self) -> bool: pass
    def istitle(self) -> bool: pass
    def isupper(self) -> bool: pass
    @overload
    def join(self, iterable: Iterable[str]) -> bytearray: pass
    @overload
    def join(self, iterable: Iterable[bytearray]) -> bytearray: pass
    @overload
    def ljust(self, width: int, fillchar: str = None) -> bytearray: pass
    @overload
    def ljust(self, width: int, fillchar: bytearray = None) -> bytearray: pass
    def lower(self) -> bytearray: pass
    @overload
    def lstrip(self, chars: str = None) -> bytearray: pass
    @overload
    def lstrip(self, chars: bytearray = None) -> bytearray: pass
    @overload
    def partition(self, sep: str) -> Tuple[bytearray, bytearray, bytearray]: pass
    @overload
    def partition(self, sep: bytearray) -> Tuple[bytearray, bytearray, bytearray]: pass
    @overload
    def replace(self, old: str, new: str, count: int = -1) -> bytearray: pass
    @overload
    def replace(self, old: bytearray, new: bytearray, count: int = -1) -> bytearray: pass
    @overload
    def rfind(self, sub: str, start: int = 0) -> int: pass
    @overload
    def rfind(self, sub: str, start: int, end: int) -> int: pass
    @overload
    def rfind(self, sub: bytearray, start: int = 0) -> int: pass
    @overload
    def rfind(self, sub: bytearray, start: int, end: int) -> int: pass
    @overload
    def rindex(self, sub: str, start: int = 0) -> int: pass
    @overload
    def rindex(self, sub: str, start: int, end: int) -> int: pass
    @overload
    def rindex(self, sub: bytearray, start: int = 0) -> int: pass
    @overload
    def rindex(self, sub: bytearray, start: int, end: int) -> int: pass
    @overload
    def rjust(self, width: int, fillchar: str = None) -> bytearray: pass
    @overload
    def rjust(self, width: int, fillchar: bytearray = None) -> bytearray: pass
    @overload
    def rpartition(self, sep: str) -> Tuple[bytearray, bytearray, bytearray]: pass
    @overload
    def rpartition(self, sep: bytearray) -> Tuple[bytearray, bytearray, bytearray]:pass
    @overload
    def rsplit(self, sep: str = None, maxsplit: int = -1) -> List[bytearray]: pass
    @overload
    def rsplit(self, sep: bytearray = None,
               maxsplit: int = -1) -> List[bytearray]: pass
    @overload
    def rstrip(self, chars: str = None) -> bytearray: pass
    @overload
    def rstrip(self, chars: bytearray = None) -> bytearray: pass
    @overload
    def split(self, sep: str = None,
              maxsplit: int = -1) -> List[bytearray]: pass
    @overload
    def split(self, sep: bytearray = None,
              maxsplit: int = -1) -> List[bytearray]: pass
    def splitlines(self, keepends: bool = False) -> List[bytearray]: pass
    @overload
    def startswith(self, prefix: str) -> bool: pass
    @overload
    def startswith(self, prefix: bytearray) -> bool: pass
    @overload
    def strip(self, chars: str = None) -> bytearray: pass
    @overload
    def strip(self, chars: bytearray = None) -> bytearray: pass
    def swapcase(self) -> bytearray: pass
    def title(self) -> bytearray: pass
    @overload
    def translate(self, table: str) -> bytearray: pass
    @overload
    def translate(self, table: bytearray) -> bytearray: pass
    def upper(self) -> bytearray: pass
    def zfill(self, width: int) -> bytearray: pass
    # TODO fromhex
    # TODO maketrans

    def __len__(self) -> int: pass
    def __iter__(self) -> Iterator[int]: pass
    def __str__(self) -> str: pass
    def __repr__(self) -> str: pass
    def __int__(self) -> int: pass
    def __float__(self) -> float: pass
    def __hash__(self) -> int: pass
    @overload
    def __getitem__(self, i: int) -> int: pass
    @overload
    def __getitem__(self, s: slice) -> bytearray: pass
    def __getslice__(self, start: int, stop: int) -> bytearray: pass
    @overload
    def __setitem__(self, i: int, x: int) -> None: pass
    @overload
    def __setitem__(self, s: slice, x: Sequence[int]) -> None: pass
    def __setslice__(self, start: int, stop: int, x: Sequence[int]) -> None: pass
    @overload
    def __delitem__(self, i: int) -> None: pass
    @overload
    def __delitem__(self, s: slice) -> None: pass
    def __delslice__(self, start: int, stop: int) -> None: pass
    @overload
    def __add__(self, s: str) -> bytearray: pass
    @overload
    def __add__(self, s: bytearray) -> bytearray: pass
    def __mul__(self, n: int) -> bytearray: pass
    def __contains__(self, o: object) -> bool: pass
    def __eq__(self, x: object) -> bool: pass
    def __ne__(self, x: object) -> bool: pass
    @overload
    def __lt__(self, x: bytearray) -> bool: pass
    @overload
    def __lt__(self, x: str) -> bool: pass
    @overload
    def __le__(self, x: bytearray) -> bool: pass
    @overload
    def __le__(self, x: str) -> bool: pass
    @overload
    def __gt__(self, x: bytearray) -> bool: pass
    @overload
    def __gt__(self, x: str) -> bool: pass
    @overload
    def __ge__(self, x: bytearray) -> bool: pass
    @overload
    def __ge__(self, x: str) -> bool: pass

@builtinclass
class bool(int, SupportsInt, SupportsFloat):
    def __init__(self, o: object = False) -> None: pass

@builtinclass
class slice:
    start = 0
    step = 0
    stop = 0
    def __init__(self, start: int, stop: int, step: int) -> None: pass

@builtinclass
class tuple(Sequence[Any]):
    @overload
    def __init__(self) -> None: pass
    @overload
    def __init__(self, iterable: Iterable[Any]) -> None: pass
    def __len__(self) -> int: pass
    def __contains__(self, x: object) -> bool: pass
    @overload
    def __getitem__(self, x: int) -> Any: pass
    @overload
    def __getitem__(self, x: slice) -> tuple: pass
    def __iter__(self) -> Iterator[Any]: pass
    def __lt__(self, x: tuple) -> bool: pass
    def __le__(self, x: tuple) -> bool: pass
    def __gt__(self, x: tuple) -> bool: pass
    def __ge__(self, x: tuple) -> bool: pass
    def __add__(self, x: tuple) -> tuple: pass

@builtinclass
class function:
    # TODO name of the class (corresponds to Python 'function' class)
    __name__ = ''
    __module__ = ''

@builtinclass
class list(Sequence[_T], Reversible[_T], AbstractGeneric[_T]):
    @overload
    def __init__(self) -> None: pass
    @overload
    def __init__(self, iterable: Iterable[_T]) -> None: pass
    def append(self, object: _T) -> None: pass
    def extend(self, iterable: Iterable[_T]) -> None: pass
    def pop(self, index: int = -1) -> _T: pass
    def index(self, object: _T, start: int = 0, stop: int = Undefined(int)) -> int: pass
    def count(self, object: _T) -> int: pass
    def insert(self, index: int, object: _T) -> None: pass
    def remove(self, object: _T) -> None: pass
    def reverse(self) -> None: pass
    def sort(self, *, key: Function[[_T], Any] = None, reverse: bool = False) -> None: pass

    def __len__(self) -> int: pass
    def __iter__(self) -> Iterator[_T]: pass
    def __str__(self) -> str: pass
    def __hash__(self) -> int: pass
    @overload
    def __getitem__(self, i: int) -> _T: pass
    @overload
    def __getitem__(self, s: slice) -> List[_T]: pass
    def __getslice__(self, start: int, stop: int) -> List[_T]: pass
    @overload
    def __setitem__(self, i: int, o: _T) -> None: pass
    @overload
    def __setitem__(self, s: slice, o: Sequence[_T]) -> None: pass
    def __setslice__(self, start: int, stop: int, o: Sequence[_T]) -> None: pass
    @overload
    def __delitem__(self, i: int) -> None: pass
    @overload
    def __delitem__(self, s: slice) -> None: pass
    def __delslice(self, start: int, stop: int) -> None: pass
    def __add__(self, x: List[_T]) -> List[_T]: pass
    def __mul__(self, n: int) -> List[_T]: pass
    def __rmul__(self, n: int) -> List[_T]: pass
    def __contains__(self, o: object) -> bool: pass
    def __reversed__(self) -> Iterator[_T]: pass
    def __gt__(self, x: List[_T]) -> bool: pass
    def __ge__(self, x: List[_T]) -> bool: pass
    def __lt__(self, x: List[_T]) -> bool: pass
    def __le__(self, x: List[_T]) -> bool: pass

@builtinclass
class dict(Mapping[_KT, _VT], Generic[_KT, _VT]):
    @overload
    def __init__(self) -> None: pass
    @overload
    def __init__(self, map: Mapping[_KT, _VT]) -> None: pass
    @overload
    def __init__(self, iterable: Iterable[Tuple[_KT, _VT]]) -> None: pass  # TODO keyword args
    def has_key(self, k: _KT) -> bool: pass
    def clear(self) -> None: pass
    def copy(self) -> Dict[_KT, _VT]: pass
    @overload
    def get(self, k: _KT) -> _VT: pass
    @overload
    def get(self, k: _KT, default: _VT) -> _VT: pass
    @overload
    def pop(self, k: _KT) -> _VT: pass
    @overload
    def pop(self, k: _KT, default: _VT) -> _VT: pass
    def popitem(self) -> Tuple[_KT, _VT]: pass
    @overload
    def setdefault(self, k: _KT) -> _VT: pass
    @overload
    def setdefault(self, k: _KT, default: _VT) -> _VT: pass
    @overload
    def update(self, m: Mapping[_KT, _VT]) -> None: pass
    @overload
    def update(self, m: Iterable[Tuple[_KT, _VT]]) -> None: pass
    def keys(self) -> List[_KT]: pass
    def values(self) -> List[_VT]: pass
    def items(self) -> List[Tuple[_KT, _VT]]: pass
    def iterkeys(self) -> Iterator[_KT]: pass
    def itervalues(self) -> Iterator[_VT]: pass
    def iteritems(self) -> Iterator[Tuple[_KT, _VT]]: pass
    def __len__(self) -> int: pass
    def __getitem__(self, k: _KT) -> _VT: pass
    def __setitem__(self, k: _KT, v: _VT) -> None: pass
    def __delitem__(self, v: _KT) -> None: pass
    def __contains__(self, o: object) -> bool: pass
    def __iter__(self) -> Iterator[_KT]: pass
    def __str__(self) -> str: pass

@builtinclass
class set(AbstractSet[_T], Generic[_T]):
    @overload
    def __init__(self) -> None: pass
    @overload
    def __init__(self, iterable: Iterable[_T]) -> None: pass
    def add(self, element: _T) -> None: pass
    def remove(self, element: _T) -> None: pass
    def copy(self) -> AbstractSet[_T]: pass
    def isdisjoint(self, s: AbstractSet[_T]) -> bool: pass
    def __len__(self) -> int: pass
    def __contains__(self, o: object) -> bool: pass
    def __iter__(self) -> Iterator[_T]: pass
    def __str__(self) -> str: pass
    def __and__(self, s: AbstractSet[_T]) -> AbstractSet[_T]: pass
    def __or__(self, s: AbstractSet[_T]) -> AbstractSet[_T]: pass
    def __sub__(self, s: AbstractSet[_T]) -> AbstractSet[_T]: pass
    def __xor__(self, s: AbstractSet[_T]) -> AbstractSet[_T]: pass
    # TODO more set operations

@builtinclass
class frozenset(AbstractSet[_T], Generic[_T]):
    @overload
    def __init__(self) -> None: pass
    @overload
    def __init__(self, iterable: Iterable[_T]) -> None: pass
    def isdisjoint(self, s: AbstractSet[_T]) -> bool: pass
    def __len__(self) -> int: pass
    def __contains__(self, o: object) -> bool: pass
    def __iter__(self) -> Iterator[_T]: pass
    def __str__(self) -> str: pass
    def __and__(self, s: AbstractSet[_T]) -> frozenset[_T]: pass
    def __or__(self, s: AbstractSet[_T]) -> frozenset[_T]: pass
    def __sub__(self, s: AbstractSet[_T]) -> frozenset[_T]: pass
    def __xor__(self, s: AbstractSet[_T]) -> frozenset[_T]: pass
    # TODO more set operations

@builtinclass
class enumerate(Iterator[Tuple[int, _T]], Generic[_T]):
    def __init__(self, iterable: Iterable[_T], start: int = 0) -> None: pass
    def __iter__(self) -> Iterator[Tuple[int, _T]]: pass
    def next(self) -> Tuple[int, _T]: pass
    # TODO __getattribute__

@builtinclass
class xrange(Sized, Iterable[int], Reversible[int]):
    @overload
    def __init__(self, stop: int) -> None: pass
    @overload
    def __init__(self, start: int, stop: int, step: int = 1) -> None: pass
    def __len__(self) -> int: pass
    def __iter__(self) -> Iterator[int]: pass
    def __getitem__(self, i: int) -> int: pass
    def __reversed__(self) -> Iterator[int]: pass

@builtinclass
class module:
    __name__ = ''
    __file__ = ''
    __dict__ = Undefined # type: Dict[unicode, Any]

True = Undefined # type: bool
False = Undefined # type: bool
__debug__ = False

long = int
bytes = str

NotImplemented = Undefined  # type: Any

def abs(n: SupportsAbs[_T]) -> _T: pass
def all(i: Iterable) -> bool: pass
def any(i: Iterable) -> bool: pass
def callable(o: object) -> bool: pass
def chr(code: int) -> str: pass
def delattr(o: Any, name: unicode) -> None: pass
def dir(o: object = None) -> List[str]: pass
@overload
def divmod(a: int, b: int) -> Tuple[int, int]: pass
@overload
def divmod(a: float, b: float) -> Tuple[float, float]: pass
def filter(function: Function[[_T], Any],
           iterable: Iterable[_T]) -> List[_T]: pass
def format(o: object, format_spec: str = '') -> str: pass  # TODO unicode
def getattr(o: Any, name: unicode, default: Any = None) -> Any: pass
def hasattr(o: Any, name: unicode) -> bool: pass
def hash(o: object) -> int: pass
def hex(i: int) -> str: pass  # TODO __index__
def id(o: object) -> int: pass
def input(prompt: unicode = None) -> Any: pass
@overload
def iter(iterable: Iterable[_T]) -> Iterator[_T]: pass
@overload
def iter(function: Function[[], _T], sentinel: _T) -> Iterator[_T]: pass
@overload
def isinstance(o: object, t: type) -> bool: pass
@overload
def isinstance(o: object, t: tuple) -> bool: pass
def issubclass(cls: type, classinfo: type) -> bool: pass
# TODO support this
#def issubclass(type cld, classinfo: Sequence[type]) -> bool: pass
def len(o: Sized) -> int: pass
@overload
def map(func: Function[[_T1], _S], iter1: Iterable[_T1]) -> List[_S]: pass
@overload
def map(func: Function[[_T1, _T2], _S],
        iter1: Iterable[_T1],
        iter2: Iterable[_T2]) -> List[_S]: pass  # TODO more than two iterables
@overload
def max(iterable: Iterable[_T]) -> _T: pass  # TODO keyword argument key
@overload
def max(arg1: _T, arg2: _T, *args: _T) -> _T: pass
# TODO memoryview
@overload
def min(iterable: Iterable[_T]) -> _T: pass
@overload
def min(arg1: _T, arg2: _T, *args: _T) -> _T: pass
@overload
def next(i: Iterator[_T]) -> _T: pass
@overload
def next(i: Iterator[_T], default: _T) -> _T: pass
def oct(i: int) -> str: pass  # TODO __index__
@overload
def open(file: unicode, mode: unicode = 'r', buffering: int = -1) -> BinaryIO: pass
@overload
def open(file: int, mode: unicode = 'r', buffering: int = -1) -> BinaryIO: pass
@overload
def ord(c: unicode) -> int: pass
@overload
def ord(c: bytearray) -> int: pass
# This is only available after from __future__ import print_function.
def print(*values: Any, sep: unicode = u' ', end: unicode = u'\n',
           file: IO[Any] = None) -> None: pass
@overload
def pow(x: int, y: int) -> Any: pass  # The return type can be int or float, depending on y.
@overload
def pow(x: int, y: int, z: int) -> Any: pass
@overload
def pow(x: float, y: float) -> float: pass
@overload
def pow(x: float, y: float, z: float) -> float: pass
def range(x: int, y: int = 0, step: int = 1) -> List[int]: pass
def raw_input(prompt: unicode = None) -> str: pass
@overload
def reversed(object: Reversible[_T]) -> Iterator[_T]: pass
@overload
def reversed(object: Sequence[_T]) -> Iterator[_T]: pass
def repr(o: object) -> str: pass
@overload
def round(number: float) -> int: pass
@overload
def round(number: float, ndigits: int) -> float: pass  # Always return a float if given ndigits.
@overload
def round(number: SupportsRound[_T]) -> _T: pass
@overload
def round(number: SupportsRound[_T], ndigits: int) -> _T: pass
def setattr(object: Any, name: unicode, value: Any) -> None: pass
def sorted(iterable: Iterable[_T], *,
           cmp: Function[[_T, _T], int] = None,
           key: Function[[_T], Any] = None,
           reverse: bool = False) -> List[_T]: pass
def sum(iterable: Iterable[_T], start: _T = None) -> _T: pass
@overload
def zip(iter1: Iterable[_T1]) -> List[Tuple[_T1]]: pass
@overload
def zip(iter1: Iterable[_T1],
        iter2: Iterable[_T2]) -> List[Tuple[_T1, _T2]]: pass
@overload
def zip(iter1: Iterable[_T1], iter2: Iterable[_T2],
        iter3: Iterable[_T3]) -> List[Tuple[_T1, _T2, _T3]]: pass
@overload
def zip(iter1: Iterable[_T1], iter2: Iterable[_T2], iter3: Iterable[_T3],
        iter4: Iterable[_T4]) -> List[Tuple[_T1, _T2,
                                           _T3, _T4]]: pass  # TODO more than four iterables
def __import__(name: unicode,
               globals: Dict[str, Any] = {},
               locals: Dict[str, Any] = {},
               fromlist: List[str] = [], level: int = -1) -> Any: pass

# Exceptions

@builtinclass
class BaseException:
    args = Undefined # type: Any
    def __init__(self, *args: Any) -> None: pass
    def with_traceback(self, tb: Any) -> BaseException: pass

class GeneratorExit(BaseException): pass
class KeyboardInterrupt(BaseException): pass
class SystemExit(BaseException):
    code = 0
class Exception(BaseException): pass
class StopIteration(Exception): pass
class StandardError(Exception): pass
class ArithmeticError(StandardError): pass
@builtinclass
class EnvironmentError(StandardError):
    errno = 0
    strerror = ''
    filename = '' # TODO can this be unicode?
class LookupError(StandardError): pass
class RuntimeError(StandardError): pass
class ValueError(StandardError): pass
class AssertionError(StandardError): pass
class AttributeError(StandardError): pass
class EOFError(StandardError): pass
class FloatingPointError(ArithmeticError): pass
class IOError(EnvironmentError): pass
class ImportError(StandardError): pass
class IndexError(LookupError): pass
class KeyError(LookupError): pass
class MemoryError(StandardError): pass
class NameError(StandardError): pass
class NotImplementedError(RuntimeError): pass
class OSError(EnvironmentError): pass
class WindowsError(OSError): pass  # TODO Windows-only
# TODO: VMSError?
class OverflowError(ArithmeticError): pass
class ReferenceError(StandardError): pass
class SyntaxError(StandardError): pass
class IndentationError(SyntaxError): pass
class TabError(IndentationError): pass
class SystemError(StandardError): pass
class TypeError(StandardError): pass
class UnboundLocalError(NameError): pass
class UnicodeError(ValueError): pass
class UnicodeDecodeError(UnicodeError): pass
class UnicodeEncodeError(UnicodeError): pass
class UnicodeTranslateError(UnicodeError): pass
class ZeroDivisionError(ArithmeticError): pass

class Warning(Exception): pass
class UserWarning(Warning): pass
class DeprecationWarning(Warning): pass
class SyntaxWarning(Warning): pass
class RuntimeWarning(Warning): pass
class FutureWarning(Warning): pass
class PendingDeprecationWarning(Warning): pass
class ImportWarning(Warning): pass
class UnicodeWarning(Warning): pass
class BytesWarning(Warning): pass
class ResourceWarning(Warning): pass
