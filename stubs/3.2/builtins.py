# Stubs for builtins

from typing import (
    Undefined, typevar, AbstractGeneric, Iterator, Iterable, overload,
    Sequence, Mapping, Tuple, List, Any, Dict, Function, Generic, Set,
    AbstractSet, Sized, Reversible, SupportsInt, SupportsFloat, SupportsAbs,
    SupportsRound, IO, builtinclass, ducktype, Union
)
from abc import abstractmethod, ABCMeta

# Note that names imported above are not automatically made visible via the
# implicit builtins import.

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

_byte_types = Union[bytes, bytearray]

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
    __dict__ = Undefined # type: Dict[str, Any]

    def __init__(self, o: object) -> None: pass

@builtinclass
@ducktype(float)
class int(SupportsInt, SupportsFloat, SupportsAbs[int]):
    def __init__(self, x: Union[SupportsInt, str, _byte_types]=None, base: int=None) -> None: pass
    def bit_length(self) -> int: pass
    def to_bytes(self, length: int, byteorder: str, *, signed: bool = False) -> bytes: pass
    @classmethod
    def from_bytes(cls, bytes: Sequence[int], byteorder: str, *,
                   signed: bool = False) -> int: pass  # TODO buffer object argument

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
@ducktype(complex)
class float(SupportsFloat, SupportsInt, SupportsAbs[float]):
    def __init__(self, x: Union[SupportsFloat, str, _byte_types]=None) -> None: pass
    def as_integer_ratio(self) -> Tuple[int, int]: pass
    def hex(self) -> str: pass
    def is_integer(self) -> bool: pass
    @classmethod
    def fromhex(cls, s: str) -> float: pass

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
    def __float__(self) -> float: pass
    def __abs__(self) -> float: pass
    def __hash__(self) -> int: pass

@builtinclass
class complex:
    def __init__(self, re: float, im: float = 0.0) -> None: pass
    # TODO this is just a placeholder; add more members

@builtinclass
class str(Sequence[str]):
    @overload
    def __init__(self) -> None: pass
    @overload
    def __init__(self, o: object) -> None: pass
    @overload
    def __init__(self, o: _byte_types, encoding: str = None, errors: str = 'strict') -> None: pass
    def capitalize(self) -> str: pass
    def center(self, width: int, fillchar: str = ' ') -> str: pass
    def count(self, x: str) -> int: pass
    def encode(self, encoding: str = 'utf-8', errors: str = 'strict') -> bytes: pass
    def endswith(self, suffix: str, start: int = 0,
                 end: int = None) -> bool: pass  # TODO tuple suffix; None value for int
    def expandtabs(self, tabsize: int = 8) -> str: pass
    def find(self, sub: str, start: int = 0, end: int = 0) -> int: pass
    def format(self, *args: Any, **kwargs: Any) -> str: pass
    def format_map(self, map: Mapping[str, Any]) -> str: pass
    def index(self, sub: str, start: int = 0, end: int = 0) -> int: pass
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
    def rfind(self, sub: str, start: int = 0, end: int = 0) -> int: pass
    def rindex(self, sub: str, start: int = 0, end: int = 0) -> int: pass
    def rjust(self, width: int, fillchar: str = ' ') -> str: pass
    def rpartition(self, sep: str) -> Tuple[str, str, str]: pass
    def rsplit(self, sep: str = None, maxsplit: int = -1) -> List[str]: pass
    def rstrip(self, chars: str = None) -> str: pass
    def split(self, sep: str = None, maxsplit: int = -1) -> List[str]: pass
    def splitlines(self, keepends: bool = False) -> List[str]: pass
    def startswith(self, prefix: str, start: int = 0,
                   end: int = None) -> bool: pass  # TODO tuple prefix; None value for int
    def strip(self, chars: str = None) -> str: pass
    def swapcase(self) -> str: pass
    def title(self) -> str: pass
    def translate(self, table: Dict[int, Any]) -> str: pass
    def upper(self) -> str: pass
    def zfill(self, width: int) -> str: pass
    # TODO maketrans

    def __getitem__(self, i: Union[int, slice]) -> str: pass
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
    def center(self, width: int, fillchar: _byte_types = None) -> bytes: pass
    def count(self, x: _byte_types) -> int: pass
    def decode(self, encoding: str = 'utf-8', errors: str = 'strict') -> str: pass
    def endswith(self, suffix: _byte_types) -> bool: pass
    def expandtabs(self, tabsize: int = 8) -> bytes: pass
    def find(self, sub: _byte_types, start: int = 0, end: int = 0) -> int: pass
    def index(self, sub: _byte_types, start: int = 0, end: int = 0) -> int: pass
    def isalnum(self) -> bool: pass
    def isalpha(self) -> bool: pass
    def isdigit(self) -> bool: pass
    def islower(self) -> bool: pass
    def isspace(self) -> bool: pass
    def istitle(self) -> bool: pass
    def isupper(self) -> bool: pass
    def join(self, iterable: Iterable[_byte_types]) -> bytes: pass
    def ljust(self, width: int, fillchar: _byte_types = None) -> bytes: pass
    def lower(self) -> bytes: pass
    def lstrip(self, chars: _byte_types = None) -> bytes: pass
    def partition(self, sep: _byte_types) -> Tuple[bytes, bytes, bytes]: pass
    def replace(self, old: _byte_types, new: _byte_types, count: int = -1) -> bytes: pass
    def rfind(self, sub: _byte_types, start: int = 0, end: int = 0) -> int: pass
    def rindex(self, sub: _byte_types, start: int = 0, end: int = 0) -> int: pass
    def rjust(self, width: int, fillchar: _byte_types = None) -> bytes: pass
    def rpartition(self, sep: _byte_types) -> Tuple[bytes, bytes, bytes]: pass
    def rsplit(self, sep: _byte_types = None, maxsplit: int = -1) -> List[bytes]: pass
    def rstrip(self, chars: _byte_types = None) -> bytes: pass
    def split(self, sep: _byte_types = None, maxsplit: int = -1) -> List[bytes]: pass
    def splitlines(self, keepends: bool = False) -> List[bytes]: pass
    def startswith(self, prefix: _byte_types) -> bool: pass
    def strip(self, chars: _byte_types = None) -> bytes: pass
    def swapcase(self) -> bytes: pass
    def title(self) -> bytes: pass
    def translate(self, table: _byte_types) -> bytes: pass
    def upper(self) -> bytes: pass
    def zfill(self, width: int) -> bytes: pass
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
    def __getitem__(self, s: slice) -> bytes: pass
    def __add__(self, s: _byte_types) -> bytes: pass
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
    @overload
    def __init__(self, ints: Iterable[int]) -> None: pass
    @overload
    def __init__(self, string: str, encoding: str, errors: str = 'strict') -> None: pass
    @overload
    def __init__(self, length: int) -> None: pass
    @overload
    def __init__(self) -> None: pass
    def capitalize(self) -> bytearray: pass
    def center(self, width: int, fillchar: _byte_types = None) -> bytearray: pass
    def count(self, x: _byte_types) -> int: pass
    def decode(self, encoding: str = 'utf-8', errors: str = 'strict') -> str: pass
    def endswith(self, suffix: _byte_types) -> bool: pass
    def expandtabs(self, tabsize: int = 8) -> bytearray: pass
    def find(self, sub: _byte_types, start: int = 0, end: int = 0) -> int: pass
    def index(self, sub: _byte_types, start: int = 0, end: int = 0) -> int: pass
    def isalnum(self) -> bool: pass
    def isalpha(self) -> bool: pass
    def isdigit(self) -> bool: pass
    def islower(self) -> bool: pass
    def isspace(self) -> bool: pass
    def istitle(self) -> bool: pass
    def isupper(self) -> bool: pass
    def join(self, iterable: Iterable[_byte_types]) -> bytearray: pass
    def ljust(self, width: int, fillchar: _byte_types = None) -> bytearray: pass
    def lower(self) -> bytearray: pass
    def lstrip(self, chars: _byte_types = None) -> bytearray: pass
    def partition(self, sep: _byte_types) -> Tuple[bytearray, bytearray, bytearray]: pass
    def replace(self, old: _byte_types, new: bytes, count: int = -1) -> bytearray: pass
    def rfind(self, sub: _byte_types, start: int = 0, end: int = 0) -> int: pass
    def rindex(self, sub: _byte_types, start: int = 0, end: int = 0) -> int: pass
    def rjust(self, width: int, fillchar: _byte_types = None) -> bytearray: pass
    def rpartition(self, sep: _byte_types) -> Tuple[bytearray, bytearray, bytearray]: pass
    def rsplit(self, sep: _byte_types = None, maxsplit: int = -1) -> List[bytearray]: pass
    def rstrip(self, chars: _byte_types = None) -> bytearray: pass
    def split(self, sep: _byte_types = None, maxsplit: int = -1) -> List[bytearray]: pass
    def splitlines(self, keepends: bool = False) -> List[bytearray]: pass
    def startswith(self, prefix: _byte_types) -> bool: pass
    def strip(self, chars: _byte_types = None) -> bytearray: pass
    def swapcase(self) -> bytearray: pass
    def title(self) -> bytearray: pass
    def translate(self, table: _byte_types) -> bytearray: pass
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
    @overload
    def __setitem__(self, i: int, x: int) -> None: pass
    @overload
    def __setitem__(self, s: slice, x: Sequence[int]) -> None: pass
    @overload
    def __delitem__(self, i: int) -> None: pass
    @overload
    def __delitem__(self, s: slice) -> None: pass
    def __add__(self, s: _byte_types) -> bytearray: pass
    def __iadd__(self, s: _byte_types) -> bytearray: pass
    def __mul__(self, n: int) -> bytearray: pass
    def __rmul__(self, n: int) -> bytearray: pass
    def __imul__(self, n: int) -> bytearray: pass
    def __contains__(self, o: object) -> bool: pass
    def __eq__(self, x: object) -> bool: pass
    def __ne__(self, x: object) -> bool: pass
    def __lt__(self, x: _byte_types) -> bool: pass
    def __le__(self, x: _byte_types) -> bool: pass
    def __gt__(self, x: _byte_types) -> bool: pass
    def __ge__(self, x: _byte_types) -> bool: pass

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
    def __add__(self, x: tuple) -> tuple: pass

@builtinclass
class function:
    # TODO not defined in builtins!
    __name__ = ''
    __module__ = ''
    __code__ = Undefined(Any)

@builtinclass
class list(Sequence[_T], Reversible[_T], AbstractGeneric[_T]):
    @overload
    def __init__(self) -> None: pass
    @overload
    def __init__(self, iterable: Iterable[_T]) -> None: pass
    def clear(self) -> None: pass
    def copy(self) -> List[_T]: pass
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
    @overload
    def __setitem__(self, i: int, o: _T) -> None: pass
    @overload
    def __setitem__(self, s: slice, o: Sequence[_T]) -> None: pass
    @overload
    def __delitem__(self, i: int) -> None: pass
    @overload
    def __delitem__(self, s: slice) -> None: pass
    def __add__(self, x: List[_T]) -> List[_T]: pass
    def __iadd__(self, x: Iterable[_T]) -> List[_T]: pass
    def __mul__(self, n: int) -> List[_T]: pass
    def __rmul__(self, n: int) -> List[_T]: pass
    def __imul__(self, n: int) -> List[_T]: pass
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
    def clear(self) -> None: pass
    def copy(self) -> Dict[_KT, _VT]: pass
    def get(self, k: _KT, default: _VT=None) -> _VT: pass
    def pop(self, k: _KT, default: _VT=None) -> _VT: pass
    def popitem(self) -> Tuple[_KT, _VT]: pass
    def setdefault(self, k: _KT, default: _VT=None) -> _VT: pass
    @overload
    def update(self, m: Mapping[_KT, _VT]) -> None: pass
    @overload
    def update(self, m: Iterable[Tuple[_KT, _VT]]) -> None: pass
    def keys(self) -> Set[_KT]: pass
    def values(self) -> Set[_VT]: pass
    def items(self) -> Set[Tuple[_KT, _VT]]: pass
    @staticmethod
    @overload
    def fromkeys(seq: Sequence[_T]) -> Dict[_T, Any]: pass  # TODO: Actually a class method
    @staticmethod
    @overload
    def fromkeys(seq: Sequence[_T], value: _S) -> Dict[_T, _S]: pass
    def __len__(self) -> int: pass
    def __getitem__(self, k: _KT) -> _VT: pass
    def __setitem__(self, k: _KT, v: _VT) -> None: pass
    def __delitem__(self, v: _KT) -> None: pass
    def __contains__(self, o: object) -> bool: pass
    def __iter__(self) -> Iterator[_KT]: pass
    def __str__(self) -> str: pass

@builtinclass
class set(AbstractSet[_T], Generic[_T]):
    def __init__(self, iterable: Iterable[_T]=None) -> None: pass
    def add(self, element: _T) -> None: pass
    def clear(self) -> None: pass
    def copy(self) -> set[_T]: pass
    def difference(self, s: Iterable[Any]) -> set[_T]: pass
    def difference_update(self, s: Iterable[Any]) -> None: pass
    def discard(self, element: _T) -> None: pass
    def intersection(self, s: Iterable[Any]) -> set[_T]: pass
    def intersection_update(self, s: Iterable[Any]) -> None: pass
    def isdisjoint(self, s: AbstractSet[Any]) -> bool: pass
    def issubset(self, s: AbstractSet[Any]) -> bool: pass
    def issuperset(self, s: AbstractSet[Any]) -> bool: pass
    def pop(self) -> _T: pass
    def remove(self, element: _T) -> None: pass
    def symmetric_difference(self, s: Iterable[_T]) -> set[_T]: pass
    def symmetric_difference_update(self, s: Iterable[_T]) -> None: pass
    def union(self, s: Iterable[_T]) -> set[_T]: pass
    def update(self, s: Iterable[_T]) -> None: pass
    def __len__(self) -> int: pass
    def __contains__(self, o: object) -> bool: pass
    def __iter__(self) -> Iterator[_T]: pass
    def __str__(self) -> str: pass
    def __and__(self, s: AbstractSet[Any]) -> set[_T]: pass
    def __iand__(self, s: AbstractSet[Any]) -> set[_T]: pass
    def __or__(self, s: AbstractSet[_T]) -> set[_T]: pass
    def __ior__(self, s: AbstractSet[_T]) -> set[_T]: pass
    def __sub__(self, s: AbstractSet[Any]) -> set[_T]: pass
    def __isub__(self, s: AbstractSet[Any]) -> set[_T]: pass
    def __xor__(self, s: AbstractSet[_T]) -> set[_T]: pass
    def __ixor__(self, s: AbstractSet[_T]) -> set[_T]: pass
    def __le__(self, s: AbstractSet[Any]) -> bool: pass
    def __lt__(self, s: AbstractSet[Any]) -> bool: pass
    def __ge__(self, s: AbstractSet[Any]) -> bool: pass
    def __gt__(self, s: AbstractSet[Any]) -> bool: pass
    # TODO more set operations

@builtinclass
class frozenset(AbstractSet[_T], Generic[_T]):
    def __init__(self, iterable: Iterable[_T]=None) -> None: pass
    def copy(self) -> frozenset[_T]: pass
    def difference(self, s: AbstractSet[Any]) -> frozenset[_T]: pass
    def intersection(self, s: AbstractSet[Any]) -> frozenset[_T]: pass
    def isdisjoint(self, s: AbstractSet[_T]) -> bool: pass
    def issubset(self, s: AbstractSet[Any]) -> bool: pass
    def issuperset(self, s: AbstractSet[Any]) -> bool: pass
    def symmetric_difference(self, s: AbstractSet[_T]) -> frozenset[_T]: pass
    def union(self, s: AbstractSet[_T]) -> frozenset[_T]: pass
    def __len__(self) -> int: pass
    def __contains__(self, o: object) -> bool: pass
    def __iter__(self) -> Iterator[_T]: pass
    def __str__(self) -> str: pass
    def __and__(self, s: AbstractSet[_T]) -> frozenset[_T]: pass
    def __or__(self, s: AbstractSet[_T]) -> frozenset[_T]: pass
    def __sub__(self, s: AbstractSet[_T]) -> frozenset[_T]: pass
    def __xor__(self, s: AbstractSet[_T]) -> frozenset[_T]: pass
    def __le__(self, s: AbstractSet[Any]) -> bool: pass
    def __lt__(self, s: AbstractSet[Any]) -> bool: pass
    def __ge__(self, s: AbstractSet[Any]) -> bool: pass
    def __gt__(self, s: AbstractSet[Any]) -> bool: pass

@builtinclass
class enumerate(Iterator[Tuple[int, _T]], Generic[_T]):
    def __init__(self, iterable: Iterable[_T], start: int = 0) -> None: pass
    def __iter__(self) -> Iterator[Tuple[int, _T]]: pass
    def __next__(self) -> Tuple[int, _T]: pass
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

def abs(n: SupportsAbs[_T]) -> _T: pass
def all(i: Iterable) -> bool: pass
def any(i: Iterable) -> bool: pass
def ascii(o: object) -> str: pass
def callable(o: object) -> bool: pass
def chr(code: int) -> str: pass
def delattr(o: Any, name: str) -> None: pass
def dir(o: object = None) -> List[str]: pass
_N = typevar('_N', values=(int, float))
def divmod(a: _N, b: _N) -> Tuple[_N, _N]: pass
def eval(source: str, globals: Dict[str, Any] = None,
         locals: Mapping[str, Any] = None) -> Any: pass  # TODO code object as source
def filter(function: Function[[_T], Any], iterable: Iterable[_T]) -> Iterator[_T]: pass
def format(o: object, format_spec: str = '') -> str: pass
def getattr(o: Any, name: str, default: Any = None) -> Any: pass
def globals() -> Dict[str, Any]: pass
def hasattr(o: Any, name: str) -> bool: pass
def hash(o: object) -> int: pass
def hex(i: int) -> str: pass  # TODO __index__
def id(o: object) -> int: pass
def input(prompt: str = None) -> str: pass
@overload
def iter(iterable: Iterable[_T]) -> Iterator[_T]: pass
@overload
def iter(function: Function[[], _T], sentinel: _T) -> Iterator[_T]: pass
def isinstance(o: object, t: Union[type, tuple]) -> bool: pass
def issubclass(cls: type, classinfo: type) -> bool: pass
# TODO support this
#def issubclass(type cld, classinfo: Sequence[type]) -> bool: pass
@overload
def len(o: Sized) -> int: pass
@overload
def len(o: tuple) -> int: pass
def locals() -> Dict[str, Any]: pass
@overload
def map(func: Function[[_T1], _S], iter1: Iterable[_T1]) -> Iterator[_S]: pass
@overload
def map(func: Function[[_T1, _T2], _S], iter1: Iterable[_T1],
        iter2: Iterable[_T2]) -> Iterator[_S]: pass  # TODO more than two iterables
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
def open(file: Union[str, bytes, int], mode: str = 'r', buffering: int = -1, encoding: str = None,
         errors: str = None, newline: str = None, closefd: bool = True) -> IO[Any]: pass
def ord(c: Union[str, bytes, bytearray]) -> int: pass
def print(*values: Any, sep: str = ' ', end: str = '\n', file: IO[str] = None) -> None: pass
@overload
def pow(x: int, y: int) -> Any: pass  # The return type can be int or float, depending on y
@overload
def pow(x: int, y: int, z: int) -> Any: pass
@overload
def pow(x: float, y: float) -> float: pass
@overload
def pow(x: float, y: float, z: float) -> float: pass
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
def setattr(object: Any, name: str, value: Any) -> None: pass
def sorted(iterable: Iterable[_T], *, key: Function[[_T], Any] = None,
           reverse: bool = False) -> List[_T]: pass
def sum(iterable: Iterable[_T], start: _T = None) -> _T: pass
@overload
def zip(iter1: Iterable[_T1]) -> Iterator[Tuple[_T1]]: pass
@overload
def zip(iter1: Iterable[_T1], iter2: Iterable[_T2]) -> Iterator[Tuple[_T1, _T2]]: pass
@overload
def zip(iter1: Iterable[_T1], iter2: Iterable[_T2],
        iter3: Iterable[_T3]) -> Iterator[Tuple[_T1, _T2, _T3]]: pass
@overload
def zip(iter1: Iterable[_T1], iter2: Iterable[_T2], iter3: Iterable[_T3],
        iter4: Iterable[_T4]) -> Iterator[Tuple[_T1, _T2,
                                               _T3, _T4]]: pass # TODO more than four iterables
def __import__(name: str, globals: Dict[str, Any] = {}, locals: Dict[str, Any] = {},
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
class Exception(BaseException): pass
class ArithmeticError(Exception): pass
@builtinclass
class EnvironmentError(Exception):
    errno = 0
    strerror = ''
    filename = ''  # TODO can this be bytes?
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
class WindowsError(OSError): pass  # TODO Windows-only
# TODO: VMSError?
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
