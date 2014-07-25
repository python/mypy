"""Stubs for builtins"""

from typing import (
    Undefined, typevar, AbstractGeneric, Iterator, Iterable, overload,
    Sequence, Mapping, Tuple, List, Any, Dict, Function, Generic, Set,
    AbstractSet, Sized, Reversible, SupportsInt, SupportsFloat, SupportsAbs,
    SupportsRound, IO, builtinclass, ducktype
)
from abc import abstractmethod, ABCMeta

# Note that names imported above are not automatically made visible via the
# implicit builtins import.

T = typevar('T')
KT = typevar('KT')
VT = typevar('VT')
S = typevar('S')
T1 = typevar('T1')
T2 = typevar('T2')
T3 = typevar('T3')
T4 = typevar('T4')


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


# Classes


@builtinclass
class type:
    __name__ = ''
    __module__ = ''
    __dict__ = Undefined # type: Dict[str, Any]
    
    def __init__(self, o: object) -> None: pass


@builtinclass
@ducktype(float)
class int(SupportsInt, SupportsFloat):
    @overload
    def __init__(self) -> None: pass
    @overload
    def __init__(self, x: SupportsInt) -> None: pass
    @overload
    def __init__(self, x: str) -> None: pass
    @overload
    def __init__(self, x: bytes) -> None: pass
    @overload
    def __init__(self, x: bytearray) -> None: pass
    @overload
    def __init__(self, string: str, base: int) -> None: pass
    @overload
    def __init__(self, string: bytes, base: int) -> None: pass
    @overload
    def __init__(self, string: bytearray, base: int) -> None: pass

    def bit_length(self) -> int: pass
    def to_bytes(self, length: int, byteorder: str, *,
                 signed: bool = False) -> bytes: pass

    # TODO buffer object argument
    @classmethod
    def from_bytes(cls, bytes: Sequence[int], byteorder: str, *,
                   signed: bool = False) -> int: pass

    def __add__(self, x: int) -> int: pass
    def __sub__(self, x: int) -> int: pass
    def __mul__(self, x: int) -> int: pass
    def __floordiv__(self, x: int) -> int: pass
    def __truediv__(self, x: int) -> float: pass
    def __mod__(self, x: int) -> int: pass
    
    def __radd__(self, x: int) -> int: pass
    def __rsub__(self, x: int) -> int: pass
    def __rmul__(self, x: int) -> int: pass
    def __rfloordiv__(self, x: int) -> int: pass
    def __rtruediv__(self, x: int) -> float: pass
    def __rmod__(self, x: int) -> int: pass
    
    # Return type can be int or float, depending on the value of x.
    def __pow__(self, x: int) -> Any: pass
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

    # Conversions

    def __str__(self) -> str: pass
    def __float__(self) -> float: pass
    def __int__(self) -> int: return self
    
    def __hash__(self) -> int: pass

    
@builtinclass
@ducktype(complex)
class float(SupportsFloat, SupportsInt):
    @overload
    def __init__(self) -> None: pass
    @overload
    def __init__(self, x: SupportsFloat) -> None: pass
    @overload
    def __init__(self, x: str) -> None: pass
    @overload
    def __init__(self, x: bytes) -> None: pass
    @overload
    def __init__(self, x: bytearray) -> None: pass

    def as_integer_ratio(self) -> Tuple[int, int]: pass
    def hex(self) -> str: pass
    def is_integer(self) -> bool: pass

    # TODO actually classmethod
    @classmethod
    def fromhex(cls, s: str) -> float: pass

    # Operators
    
    def __add__(self, x: float) -> float: pass
    def __sub__(self, x: float) -> float: pass
    def __mul__(self, x: float) -> float: pass
    def __floordiv__(self, x: float) -> float: pass
    def __truediv__(self, x: float) -> float: pass
    def __mod__(self, x: float) -> float: pass
    def __pow__(self, x: float) -> float: pass
    
    def __radd__(self, x: float) -> float: pass
    def __rsub__(self, x: float) -> float: pass
    def __rmul__(self, x: float) -> float: pass
    def __rfloordiv__(self, x: float) -> float: pass
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
    def __hash__(self) -> int: pass


@builtinclass
class complex:
    # TODO this is just a placeholder; add more members
    def __init__(self, re: float, im: float = 0.0) -> None: pass


@builtinclass
class str(Sequence[str]):
    # TODO maketrans
    
    @overload
    def __init__(self) -> None: pass
    @overload
    def __init__(self, o: object) -> None: pass
    @overload
    def __init__(self, o: bytes, encoding: str = None,
                 errors: str = 'strict') -> None: pass
    @overload
    def __init__(self, o: bytearray, encoding: str = None,
                 errors: str = 'strict') -> None: pass

    def capitalize(self) -> str: pass
    def center(self, width: int, fillchar: str = ' ') -> str: pass
    def count(self, x: str) -> int: pass
    def encode(self, encoding: str = 'utf-8',
               errors: str = 'strict') -> bytes: pass
    # TODO tuple suffix; None value for int
    def endswith(self, suffix: str, start: int = 0,
                 end: int = None) -> bool: pass
    def expandtabs(self, tabsize: int = 8) -> str: pass
    
    @overload
    def find(self, sub: str, start: int = 0) -> int: pass
    @overload
    def find(self, sub: str, start: int, end: int) -> int: pass
    
    def format(self, *args: Any, **kwargs: Any) -> str: pass
    def format_map(self, map: Mapping[str, Any]) -> str: pass
    
    @overload
    def index(self, sub: str, start: int = 0) -> int: pass
    @overload
    def index(self, sub: str, start: int, end: int) -> int: pass
    
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
    def join(self, iterable: Iterable[str]) -> str: pass
    def ljust(self, width: int, fillchar: str = ' ') -> str: pass
    def lower(self) -> str: pass
    def lstrip(self, chars: str = None) -> str: pass
    def partition(self, sep: str) -> Tuple[str, str, str]: pass
    def replace(self, old: str, new: str, count: int = -1) -> str: pass
    
    @overload
    def rfind(self, sub: str, start: int = 0) -> int: pass
    @overload
    def rfind(self, sub: str, start: int, end: int) -> int: pass
    @overload
    def rindex(self, sub: str, start: int = 0) -> int: pass
    @overload
    def rindex(self, sub: str, start: int, end: int) -> int: pass
    
    def rjust(self, width: int, fillchar: str = ' ') -> str: pass
    def rpartition(self, sep: str) -> Tuple[str, str, str]: pass
    def rsplit(self, sep: str = None, maxsplit: int = -1) -> List[str]: pass
    def rstrip(self, chars: str = None) -> str: pass
    def split(self, sep: str = None, maxsplit: int = -1) -> List[str]: pass
    def splitlines(self, keepends: bool = False) -> List[str]: pass
    # TODO tuple prefix; None value for int
    def startswith(self, prefix: str, start: int = 0,
                   end: int = None) -> bool: pass
    def strip(self, chars: str = None) -> str: pass
    def swapcase(self) -> str: pass
    def title(self) -> str: pass
    def translate(self, table: Dict[int, Any]) -> str: pass
    def upper(self) -> str: pass
    def zfill(self, width: int) -> str: pass
    
    @overload
    def __getitem__(self, i: int) -> str: pass
    @overload
    def __getitem__(self, s: slice) -> str: pass

    def __add__(self, s: str) -> str: pass
    def __mul__(self, n: int) -> str: pass
    def __rmul__(self, n: int) -> str: pass
    def __mod__(self, *args: Any) -> str: pass
    def __eq__(self, x: object) -> bool: pass
    def __ne__(self, x: object) -> bool: pass
    def __lt__(self, x: str) -> bool: pass
    def __le__(self, x: str) -> bool: pass
    def __gt__(self, x: str) -> bool: pass
    def __ge__(self, x: str) -> bool: pass
    
    def __len__(self) -> int: pass
    def __contains__(self, s: object) -> bool: pass
    def __iter__(self) -> Iterator[str]: pass
    def __str__(self) -> str: return self
    def __repr__(self) -> str: pass
    def __int__(self) -> int: pass
    def __float__(self) -> float: pass
    def __hash__(self) -> int: pass
    

@builtinclass
class bytes(Sequence[int]):
    # TODO fromhex
    # TODO maketrans
    
    @overload
    def __init__(self, ints: Iterable[int]) -> None: pass
    @overload
    def __init__(self, string: str, encoding: str,
                 errors: str = 'strict') -> None: pass
    @overload
    def __init__(self, length: int) -> None: pass
    @overload
    def __init__(self) -> None: pass

    def capitalize(self) -> bytes: pass
    
    @overload
    def center(self, width: int, fillchar: bytes = None) -> bytes: pass
    @overload
    def center(self, width: int, fillchar: bytearray = None) -> bytes: pass
    @overload
    def count(self, x: bytes) -> int: pass
    @overload
    def count(self, x: bytearray) -> int: pass
    def decode(self, encoding: str = 'utf-8',
               errors: str = 'strict') -> str: pass
    @overload
    def endswith(self, suffix: bytes) -> bool: pass
    @overload
    def endswith(self, suffix: bytearray) -> bool: pass
    def expandtabs(self, tabsize: int = 8) -> bytes: pass
    @overload
    def find(self, sub: bytes, start: int = 0) -> int: pass
    @overload
    def find(self, sub: bytes, start: int, end: int) -> int: pass
    @overload
    def find(self, sub: bytearray, start: int = 0) -> int: pass
    @overload
    def find(self, sub: bytearray, start: int, end: int) -> int: pass
    @overload
    def index(self, sub: bytes, start: int = 0) -> int: pass
    @overload
    def index(self, sub: bytes, start: int, end: int) -> int: pass
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
    def join(self, iterable: Iterable[bytes]) -> bytes: pass
    @overload
    def join(self, iterable: Iterable[bytearray]) -> bytes: pass
    @overload
    def ljust(self, width: int, fillchar: bytes = None) -> bytes: pass
    @overload
    def ljust(self, width: int, fillchar: bytearray = None) -> bytes: pass
    def lower(self) -> bytes: pass
    @overload
    def lstrip(self, chars: bytes = None) -> bytes: pass
    @overload
    def lstrip(self, chars: bytearray = None) -> bytes: pass
    @overload
    def partition(self, sep: bytes) -> Tuple[bytes, bytes, bytes]: pass
    @overload
    def partition(self, sep: bytearray) -> Tuple[bytes, bytes, bytes]: pass
    @overload
    def replace(self, old: bytes, new: bytes, count: int = -1) -> bytes: pass
    @overload
    def replace(self, old: bytearray, new: bytearray,
                count: int = -1) -> bytes: pass
    @overload
    def rfind(self, sub: bytes, start: int = 0) -> int: pass
    @overload
    def rfind(self, sub: bytes, start: int, end: int) -> int: pass
    @overload
    def rfind(self, sub: bytearray, start: int = 0) -> int: pass
    @overload
    def rfind(self, sub: bytearray, start: int, end: int) -> int: pass
    @overload
    def rindex(self, sub: bytes, start: int = 0) -> int: pass
    @overload
    def rindex(self, sub: bytes, start: int, end: int) -> int: pass
    @overload
    def rindex(self, sub: bytearray, start: int = 0) -> int: pass
    @overload
    def rindex(self, sub: bytearray, start: int, end: int) -> int: pass
    @overload
    def rjust(self, width: int, fillchar: bytes = None) -> bytes: pass
    @overload
    def rjust(self, width: int, fillchar: bytearray = None) -> bytes: pass
    @overload
    def rpartition(self, sep: bytes) -> Tuple[bytes, bytes, bytes]: pass
    @overload
    def rpartition(self, sep: bytearray) -> Tuple[bytes, bytes, bytes]: pass
    @overload
    def rsplit(self, sep: bytes = None,
               maxsplit: int = -1) -> List[bytes]: pass
    @overload
    def rsplit(self, sep: bytearray = None,
               maxsplit: int = -1) -> List[bytes]: pass
    @overload
    def rstrip(self, chars: bytes = None) -> bytes: pass
    @overload
    def rstrip(self, chars: bytearray = None) -> bytes: pass
    @overload
    def split(self, sep: bytes = None, maxsplit: int = -1) -> List[bytes]: pass
    @overload
    def split(self, sep: bytearray = None,
              maxsplit: int = -1) -> List[bytes]: pass
    def splitlines(self, keepends: bool = False) -> List[bytes]: pass
    @overload
    def startswith(self, prefix: bytes) -> bool: pass
    @overload
    def startswith(self, prefix: bytearray) -> bool: pass
    @overload
    def strip(self, chars: bytes = None) -> bytes: pass
    @overload
    def strip(self, chars: bytearray = None) -> bytes: pass
    def swapcase(self) -> bytes: pass
    def title(self) -> bytes: pass
    @overload
    def translate(self, table: bytes) -> bytes: pass
    @overload
    def translate(self, table: bytearray) -> bytes: pass
    def upper(self) -> bytes: pass
    def zfill(self, width: int) -> bytes: pass
    
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
    def __getitem__(self, s: slice) -> bytes: pass
    @overload
    def __add__(self, s: bytes) -> bytes: pass    
    @overload
    def __add__(self, s: bytearray) -> bytes: pass
    
    def __mul__(self, n: int) -> bytes: pass
    def __rmul__(self, n: int) -> bytes: pass
    def __contains__(self, o: object) -> bool: pass    
    def __eq__(self, x: object) -> bool: pass
    def __ne__(self, x: object) -> bool: pass
    def __lt__(self, x: bytes) -> bool: pass
    def __le__(self, x: bytes) -> bool: pass
    def __gt__(self, x: bytes) -> bool: pass
    def __ge__(self, x: bytes) -> bool: pass


@builtinclass
class bytearray(Sequence[int]):
    # TODO fromhex
    # TODO maketrans
    
    @overload
    def __init__(self, ints: Iterable[int]) -> None: pass
    @overload
    def __init__(self, string: str, encoding: str,
                 errors: str = 'strict') -> None: pass
    @overload
    def __init__(self, length: int) -> None: pass
    @overload
    def __init__(self) -> None: pass

    def capitalize(self) -> bytearray: pass
    @overload
    def center(self, width: int, fillchar: bytes = None) -> bytearray: pass
    @overload
    def center(self, width: int, fillchar: bytearray = None) -> bytearray: pass
    @overload
    def count(self, x: bytes) -> int: pass
    @overload
    def count(self, x: bytearray) -> int: pass
    def decode(self, encoding: str = 'utf-8',
               errors: str = 'strict') -> str: pass
    @overload
    def endswith(self, suffix: bytes) -> bool: pass
    @overload
    def endswith(self, suffix: bytearray) -> bool: pass
    def expandtabs(self, tabsize: int = 8) -> bytearray: pass
    @overload
    def find(self, sub: bytes, start: int = 0) -> int: pass
    @overload
    def find(self, sub: bytes, start: int, end: int) -> int: pass
    @overload
    def find(self, sub: bytearray, start: int = 0) -> int: pass
    @overload
    def find(self, sub: bytearray, start: int, end: int) -> int: pass
    @overload
    def index(self, sub: bytes, start: int = 0) -> int: pass
    @overload
    def index(self, sub: bytes, start: int, end: int) -> int: pass
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
    def join(self, iterable: Iterable[bytes]) -> bytearray: pass
    @overload
    def join(self, iterable: Iterable[bytearray]) -> bytearray: pass
    @overload
    def ljust(self, width: int, fillchar: bytes = None) -> bytearray: pass
    @overload
    def ljust(self, width: int, fillchar: bytearray = None) -> bytearray: pass
    def lower(self) -> bytearray: pass
    @overload
    def lstrip(self, chars: bytes = None) -> bytearray: pass
    @overload
    def lstrip(self, chars: bytearray = None) -> bytearray: pass
    @overload
    def partition(self, sep: bytes) -> Tuple[bytearray, bytearray,
                                             bytearray]: pass
    @overload
    def partition(self, sep: bytearray) -> Tuple[bytearray, bytearray,
                                                 bytearray]: pass
    @overload
    def replace(self, old: bytes, new: bytes,
                count: int = -1) -> bytearray: pass
    @overload
    def replace(self, old: bytearray, new: bytearray,
                count: int = -1) -> bytearray: pass
    @overload
    def rfind(self, sub: bytes, start: int = 0) -> int: pass
    @overload
    def rfind(self, sub: bytes, start: int, end: int) -> int: pass
    @overload
    def rfind(self, sub: bytearray, start: int = 0) -> int: pass
    @overload
    def rfind(self, sub: bytearray, start: int, end: int) -> int: pass
    @overload
    def rindex(self, sub: bytes, start: int = 0) -> int: pass
    @overload
    def rindex(self, sub: bytes, start: int, end: int) -> int: pass
    @overload
    def rindex(self, sub: bytearray, start: int = 0) -> int: pass
    @overload
    def rindex(self, sub: bytearray, start: int, end: int) -> int: pass
    @overload
    def rjust(self, width: int, fillchar: bytes = None) -> bytearray: pass
    @overload
    def rjust(self, width: int, fillchar: bytearray = None) -> bytearray: pass
    @overload
    def rpartition(self, sep: bytes) -> Tuple[bytearray, bytearray,
                                              bytearray]: pass
    @overload
    def rpartition(self, sep: bytearray) -> Tuple[bytearray, bytearray,
                                                  bytearray]:pass
    @overload
    def rsplit(self, sep: bytes = None,
               maxsplit: int = -1) -> List[bytearray]: pass
    @overload
    def rsplit(self, sep: bytearray = None,
               maxsplit: int = -1) -> List[bytearray]: pass
    @overload
    def rstrip(self, chars: bytes = None) -> bytearray: pass
    @overload
    def rstrip(self, chars: bytearray = None) -> bytearray: pass
    @overload
    def split(self, sep: bytes = None,
              maxsplit: int = -1) -> List[bytearray]: pass
    @overload
    def split(self, sep: bytearray = None,
              maxsplit: int = -1) -> List[bytearray]: pass
    def splitlines(self, keepends: bool = False) -> List[bytearray]: pass
    @overload
    def startswith(self, prefix: bytes) -> bool: pass
    @overload
    def startswith(self, prefix: bytearray) -> bool: pass
    @overload
    def strip(self, chars: bytes = None) -> bytearray: pass
    @overload
    def strip(self, chars: bytearray = None) -> bytearray: pass
    def swapcase(self) -> bytearray: pass
    def title(self) -> bytearray: pass
    @overload
    def translate(self, table: bytes) -> bytearray: pass
    @overload
    def translate(self, table: bytearray) -> bytearray: pass
    def upper(self) -> bytearray: pass
    def zfill(self, width: int) -> bytearray: pass
    
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
    @overload
    def __setitem__(self, i: int, x: int) -> None: pass
    @overload
    def __setitem__(self, s: slice, x: Sequence[int]) -> None: pass
    @overload
    def __delitem__(self, i: int) -> None: pass
    @overload
    def __delitem__(self, s: slice) -> None: pass
    
    @overload
    def __add__(self, s: bytes) -> bytearray: pass    
    @overload
    def __add__(self, s: bytearray) -> bytearray: pass
    @overload
    def __iadd__(self, s: bytes) -> bytearray: pass    
    @overload
    def __iadd__(self, s: bytearray) -> bytearray: pass
    
    def __mul__(self, n: int) -> bytearray: pass
    def __rmul__(self, n: int) -> bytearray: pass
    def __imul__(self, n: int) -> bytearray: pass
    def __contains__(self, o: object) -> bool: pass
    def __eq__(self, x: object) -> bool: pass
    def __ne__(self, x: object) -> bool: pass
    @overload
    def __lt__(self, x: bytearray) -> bool: pass
    @overload
    def __lt__(self, x: bytes) -> bool: pass
    @overload
    def __le__(self, x: bytearray) -> bool: pass
    @overload
    def __le__(self, x: bytes) -> bool: pass
    @overload
    def __gt__(self, x: bytearray) -> bool: pass
    @overload
    def __gt__(self, x: bytes) -> bool: pass
    @overload
    def __ge__(self, x: bytearray) -> bool: pass
    @overload
    def __ge__(self, x: bytes) -> bool: pass


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
class tuple(Iterable[Any], Sized):
    @overload
    def __init__(self) -> None: pass
    @overload
    def __init__(self, iterable: Iterable[Any]) -> None: pass
    @overload
    def __init__(self, iterable: tuple) -> None: pass
    
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


@builtinclass
class function:
    # TODO not defined in builtins!
    __name__ = ''
    __module__ = ''
    __code__ = Undefined(Any)


@builtinclass
class list(Sequence[T], Reversible[T], AbstractGeneric[T]):
    @overload
    def __init__(self) -> None: pass
    @overload
    def __init__(self, iterable: Iterable[T]) -> None: pass

    def clear(self) -> None: pass
    def copy(self) -> List[T]: pass
    def append(self, object: T) -> None: pass
    def extend(self, iterable: Iterable[T]) -> None: pass
    def pop(self, index: int = -1) -> T: pass
    def index(self, object: T, start: int = 0, stop: int = Undefined(int)) -> int: pass
    def count(self, object: T) -> int: pass
    def insert(self, index: int, object: T) -> None: pass
    def remove(self, object: T) -> None: pass
    def reverse(self) -> None: pass
    def sort(self, *, key: Function[[T], Any] = None,
             reverse: bool = False) -> None: pass
    
    def __len__(self) -> int: pass
    def __iter__(self) -> Iterator[T]: pass
    def __str__(self) -> str: pass
    def __hash__(self) -> int: pass
    
    @overload
    def __getitem__(self, i: int) -> T: pass
    @overload
    def __getitem__(self, s: slice) -> List[T]: pass    
    @overload
    def __setitem__(self, i: int, o: T) -> None: pass
    @overload
    def __setitem__(self, s: slice, o: Sequence[T]) -> None: pass
    @overload
    def __delitem__(self, i: int) -> None: pass
    @overload
    def __delitem__(self, s: slice) -> None: pass
    
    def __add__(self, x: List[T]) -> List[T]: pass
    def __iadd__(self, x: Iterable[T]) -> List[T]: pass
    def __mul__(self, n: int) -> List[T]: pass
    def __rmul__(self, n: int) -> List[T]: pass
    def __imul__(self, n: int) -> List[T]: pass
    def __contains__(self, o: object) -> bool: pass
    def __reversed__(self) -> Iterator[T]: pass

    def __gt__(self, x: List[T]) -> bool: pass
    def __ge__(self, x: List[T]) -> bool: pass
    def __lt__(self, x: List[T]) -> bool: pass
    def __le__(self, x: List[T]) -> bool: pass


@builtinclass
class dict(Mapping[KT, VT], Generic[KT, VT]):
    @overload
    def __init__(self) -> None: pass
    @overload
    def __init__(self, map: Mapping[KT, VT]) -> None: pass
    @overload
    def __init__(self, iterable: Iterable[Tuple[KT, VT]]) -> None: pass
    # TODO __init__ keyword args
    
    def __len__(self) -> int: pass
    def __getitem__(self, k: KT) -> VT: pass
    def __setitem__(self, k: KT, v: VT) -> None: pass
    def __delitem__(self, v: KT) -> None: pass
    def __contains__(self, o: object) -> bool: pass
    def __iter__(self) -> Iterator[KT]: pass
    def __str__(self) -> str: pass
    
    def clear(self) -> None: pass
    def copy(self) -> Dict[KT, VT]: pass
    
    @overload
    def get(self, k: KT) -> VT: pass
    @overload
    def get(self, k: KT, default: VT) -> VT: pass
    @overload
    def pop(self, k: KT) -> VT: pass
    @overload
    def pop(self, k: KT, default: VT) -> VT: pass
    def popitem(self) -> Tuple[KT, VT]: pass
    @overload
    def setdefault(self, k: KT) -> VT: pass
    @overload
    def setdefault(self, k: KT, default: VT) -> VT: pass
    
    @overload
    def update(self, m: Mapping[KT, VT]) -> None: pass
    @overload
    def update(self, m: Iterable[Tuple[KT, VT]]) -> None: pass

    def keys(self) -> Set[KT]: pass
    def values(self) -> Set[VT]: pass
    def items(self) -> Set[Tuple[KT, VT]]: pass

    @classmethod
    @overload
    def fromkeys(cls, seq: Sequence[T]) -> Dict[T, Any]: pass
    @classmethod
    @overload
    def fromkeys(cls, seq: Sequence[T], value: S) -> Dict[T, S]: pass


@builtinclass
class set(AbstractSet[T], Generic[T]):
    @overload
    def __init__(self) -> None: pass
    @overload
    def __init__(self, iterable: Iterable[T]) -> None: pass
    
    def add(self, element: T) -> None: pass
    def clear(self) -> None: pass
    def copy(self) -> set[T]: pass
    def difference(self, s: Iterable[Any]) -> set[T]: pass
    def difference_update(self, s: Iterable[Any]) -> None: pass
    def discard(self, element: T) -> None: pass
    def intersection(self, s: Iterable[Any]) -> set[T]: pass
    def intersection_update(self, s: Iterable[Any]) -> None: pass
    def isdisjoint(self, s: AbstractSet[Any]) -> bool: pass
    def issubset(self, s: AbstractSet[Any]) -> bool: pass
    def issuperset(self, s: AbstractSet[Any]) -> bool: pass
    def pop(self) -> T: pass
    def remove(self, element: T) -> None: pass
    def symmetric_difference(self, s: Iterable[T]) -> set[T]: pass
    def symmetric_difference_update(self, s: Iterable[T]) -> None: pass
    def union(self, s: Iterable[T]) -> set[T]: pass
    def update(self, s: Iterable[T]) -> None: pass
    
    def __len__(self) -> int: pass
    def __contains__(self, o: object) -> bool: pass
    def __iter__(self) -> Iterator[T]: pass    
    def __str__(self) -> str: pass
    def __and__(self, s: AbstractSet[Any]) -> set[T]: pass
    def __iand__(self, s: AbstractSet[Any]) -> set[T]: pass
    def __or__(self, s: AbstractSet[T]) -> set[T]: pass
    def __ior__(self, s: AbstractSet[T]) -> set[T]: pass
    def __sub__(self, s: AbstractSet[Any]) -> set[T]: pass
    def __isub__(self, s: AbstractSet[Any]) -> set[T]: pass
    def __xor__(self, s: AbstractSet[T]) -> set[T]: pass
    def __ixor__(self, s: AbstractSet[T]) -> set[T]: pass
    def __le__(self, s: AbstractSet[Any]) -> bool: pass
    def __lt__(self, s: AbstractSet[Any]) -> bool: pass
    def __ge__(self, s: AbstractSet[Any]) -> bool: pass
    def __gt__(self, s: AbstractSet[Any]) -> bool: pass
    
    # TODO more set operations


@builtinclass
class frozenset(AbstractSet[T], Generic[T]):
    @overload
    def __init__(self) -> None: pass
    @overload
    def __init__(self, iterable: Iterable[T]) -> None: pass

    def copy(self) -> frozenset[T]: pass
    def difference(self, s: AbstractSet[Any]) -> frozenset[T]: pass
    def intersection(self, s: AbstractSet[Any]) -> frozenset[T]: pass
    def isdisjoint(self, s: AbstractSet[T]) -> bool: pass
    def issubset(self, s: AbstractSet[Any]) -> bool: pass
    def issuperset(self, s: AbstractSet[Any]) -> bool: pass
    def symmetric_difference(self, s: AbstractSet[T]) -> frozenset[T]: pass
    def union(self, s: AbstractSet[T]) -> frozenset[T]: pass
    
    def __len__(self) -> int: pass
    def __contains__(self, o: object) -> bool: pass
    def __iter__(self) -> Iterator[T]: pass    
    def __str__(self) -> str: pass
    def __and__(self, s: AbstractSet[T]) -> frozenset[T]: pass
    def __or__(self, s: AbstractSet[T]) -> frozenset[T]: pass
    def __sub__(self, s: AbstractSet[T]) -> frozenset[T]: pass
    def __xor__(self, s: AbstractSet[T]) -> frozenset[T]: pass
    def __le__(self, s: AbstractSet[Any]) -> bool: pass
    def __lt__(self, s: AbstractSet[Any]) -> bool: pass
    def __ge__(self, s: AbstractSet[Any]) -> bool: pass
    def __gt__(self, s: AbstractSet[Any]) -> bool: pass


@builtinclass
class enumerate(Iterator[Tuple[int, T]], Generic[T]):
    def __init__(self, iterable: Iterable[T], start: int = 0) -> None: pass
    def __iter__(self) -> Iterator[Tuple[int, T]]: pass
    def __next__(self) -> Tuple[int, T]: pass
    # TODO __getattribute__


@builtinclass
class range(Sequence[int], Reversible[int]):
    @overload
    def __init__(self, stop: int) -> None: pass
    @overload
    def __init__(self, start: int, stop: int, step: int = 1) -> None: pass
    
    def count(self, value: int) -> int: pass
    def index(self, value: int, start: int = 0, stop: int = None) -> int: pass
    
    def __len__(self) -> int: pass
    def __contains__(self, o: object) -> bool: pass
    def __iter__(self) -> Iterator[int]: pass
    @overload
    def __getitem__(self, i: int) -> int: pass
    @overload
    def __getitem__(self, s: slice) -> range: pass
    def __repr__(self) -> str: pass
    def __reversed__(self) -> Iterator[int]: pass


@builtinclass
class module:
    # TODO not defined in builtins!
    __name__ = ''
    __file__ = ''
    __dict__ = Undefined # type: Dict[str, Any]


True = Undefined # type: bool
False = Undefined # type: bool
__debug__ = False


NotImplemented = Undefined # type: Any


@overload
def abs(n: int) -> int: pass
@overload
def abs(n: float) -> float: pass
@overload
def abs(n: SupportsAbs[T]) -> T: pass

def all(i: Iterable) -> bool: pass
def any(i: Iterable) -> bool: pass
def ascii(o: object) -> str: pass
def callable(o: object) -> bool: pass
def chr(code: int) -> str: pass
def delattr(o: Any, name: str) -> None: pass
def dir(o: object = None) -> List[str]: pass

_N = typevar('_N', values=(int, float))
def divmod(a: _N, b: _N) -> Tuple[_N, _N]: pass

# TODO code object as source
def eval(source: str, globals: Dict[str, Any] = None,
         locals: Mapping[str, Any] = None) -> Any: pass

def filter(function: Function[[T], Any],
           iterable: Iterable[T]) -> Iterator[T]: pass
def format(o: object, format_spec: str = '') -> str: pass
def getattr(o: Any, name: str, default: Any = None) -> Any: pass
def globals() -> Dict[str, Any]: pass
def hasattr(o: Any, name: str) -> bool: pass
def hash(o: object) -> int: pass
# TODO __index__
def hex(i: int) -> str: pass
def id(o: object) -> int: pass
def input(prompt: str = None) -> str: pass

@overload
def iter(iterable: Iterable[T]) -> Iterator[T]: pass
@overload
def iter(function: Function[[], T], sentinel: T) -> Iterator[T]: pass

@overload
def isinstance(o: object, t: type) -> bool: pass
@overload
def isinstance(o: object, t: tuple) -> bool: pass

def issubclass(cls: type, classinfo: type) -> bool: pass
# TODO perhaps support this
#def issubclass(type cld, classinfo: Sequence[type]) -> bool: pass
@overload
def len(o: Sized) -> int: pass
@overload
def len(o: tuple) -> int: pass
def locals() -> Dict[str, Any]: pass

# TODO more than two iterables
@overload
def map(func: Function[[T1], S], iter1: Iterable[T1]) -> Iterator[S]: pass
@overload
def map(func: Function[[T1, T2], S],
        iter1: Iterable[T1],
        iter2: Iterable[T2]) -> Iterator[S]: pass

# TODO keyword argument key
@overload
def max(iterable: Iterable[T]) -> T: pass
@overload
def max(arg1: T, arg2: T, *args: T) -> T: pass

# TODO memoryview

@overload
def min(iterable: Iterable[T]) -> T: pass
@overload
def min(arg1: T, arg2: T, *args: T) -> T: pass

@overload
def next(i: Iterator[T]) -> T: pass
@overload
def next(i: Iterator[T], default: T) -> T: pass

# TODO __index__
def oct(i: int) -> str: pass

@overload
def open(file: str, mode: str = 'r', buffering: int = -1, encoding: str = None,
         errors: str = None, newline: str = None,
         closefd: bool = True) -> IO[Any]: pass
@overload
def open(file: bytes, mode: str = 'r', buffering: int = -1,
         encoding: str = None, errors: str = None, newline: str = None,
         closefd: bool = True) -> IO[Any]: pass
@overload
def open(file: int, mode: str = 'r', buffering: int = -1, encoding: str = None,
         errors: str = None, newline: str = None,
         closefd: bool = True) -> IO[Any]: pass

@overload
def ord(c: str) -> int: pass
@overload
def ord(c: bytes) -> int: pass
@overload
def ord(c: bytearray) -> int: pass

def print(*values: Any, sep: str = ' ', end: str = '\n',
           file: IO[str] = None) -> None: pass

# The return type can be int or float, depending on the value of y.
@overload
def pow(x: int, y: int) -> Any: pass
@overload
def pow(x: int, y: int, z: int) -> Any: pass
@overload
def pow(x: float, y: float) -> float: pass
@overload
def pow(x: float, y: float, z: float) -> float: pass

@overload
def reversed(object: Reversible[T]) -> Iterator[T]: pass
@overload
def reversed(object: Sequence[T]) -> Iterator[T]: pass

def repr(o: object) -> str: pass

# Always return a float if ndigits is present.
@overload
def round(number: float) -> int: pass
@overload
def round(number: float, ndigits: int) -> float: pass
@overload
def round(number: SupportsRound[T]) -> T: pass
@overload
def round(number: SupportsRound[T], ndigits: int) -> T: pass

def setattr(object: Any, name: str, value: Any) -> None: pass
def sorted(iterable: Iterable[T], *, key: Function[[T], Any] = None,
           reverse: bool = False) -> List[T]: pass
def sum(iterable: Iterable[T], start: T = None) -> T: pass

# TODO more than four iterables
@overload
def zip(iter1: Iterable[T1]) -> Iterator[Tuple[T1]]: pass
@overload
def zip(iter1: Iterable[T1],
        iter2: Iterable[T2]) -> Iterator[Tuple[T1, T2]]: pass
@overload
def zip(iter1: Iterable[T1], iter2: Iterable[T2],
        iter3: Iterable[T3]) -> Iterator[Tuple[T1, T2, T3]]: pass
@overload
def zip(iter1: Iterable[T1], iter2: Iterable[T2], iter3: Iterable[T3],
        iter4: Iterable[T4]) -> Iterator[Tuple[T1, T2, T3, T4]]: pass

def __import__(name: str,
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
@builtinclass
class SystemExit(BaseException):
    code = 0

# Base classes
class Exception(BaseException): pass
class ArithmeticError(Exception): pass
@builtinclass
class EnvironmentError(Exception):
    errno = 0
    strerror = ''
    filename = '' # TODO can this be bytes?
class LookupError(Exception): pass
class RuntimeError(Exception): pass
class ValueError(Exception): pass

class AssertionError(Exception): pass
class AttributeError(Exception): pass
class EOFError(Exception): pass
class FloatingPointError(ArithmeticError): pass
class IOError(EnvironmentError): pass
class ImportError(Exception): pass
class IndexError(LookupError): pass
class KeyError(LookupError): pass
class MemoryError(Exception): pass
class NameError(Exception): pass
class NotImplementedError(RuntimeError): pass
class OSError(EnvironmentError): pass
class OverflowError(ArithmeticError): pass
class ReferenceError(Exception): pass
class StopIteration(Exception): pass
class SyntaxError(Exception): pass
class IndentationError(SyntaxError): pass
class TabError(IndentationError): pass
class SystemError(Exception): pass
class TypeError(Exception): pass
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

# TODO Windows-only
class WindowsError(OSError): pass

# TODO: VMSError
