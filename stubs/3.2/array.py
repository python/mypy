# Stubs for array

# Based on http://docs.python.org/3.2/library/array.html

from typing import Any, Iterable, Tuple, List, Iterator, BinaryIO, overload

typecodes = ''

class array:
    def __init__(self, typecode: str,
                 initializer: Iterable[Any] = None) -> None:
        typecode = ''
        itemsize = 0

    def append(self, x: Any) -> None: pass
    def buffer_info(self) -> Tuple[int, int]: pass
    def byteswap(self) -> None: pass
    def count(self, x: Any) -> int: pass
    def extend(self, iterable: Iterable[Any]) -> None: pass
    def frombytes(self, s: bytes) -> None: pass
    def fromfile(self, f: BinaryIO, n: int) -> None: pass
    def fromlist(self, list: List[Any]) -> None: pass
    def fromstring(self, s: bytes) -> None: pass
    def fromunicode(self, s: str) -> None: pass
    def index(self, x: Any) -> int: pass
    def insert(self, i: int, x: Any) -> None: pass
    def pop(self, i: int = -1) -> Any: pass
    def remove(self, x: Any) -> None: pass
    def reverse(self) -> None: pass
    def tobytes(self) -> bytes: pass
    def tofile(self, f: BinaryIO) -> None: pass
    def tolist(self) -> List[Any]: pass
    def tostring(self) -> bytes: pass
    def tounicode(self) -> str: pass

    def __len__(self) -> int: pass
    def __iter__(self) -> Iterator[Any]: pass
    def __str__(self) -> str: pass
    def __hash__(self) -> int: pass

    @overload
    def __getitem__(self, i: int) -> Any: pass
    @overload
    def __getitem__(self, s: slice) -> 'array': pass

    def __setitem__(self, i: int, o: Any) -> None: pass
    def __delitem__(self, i: int) -> None: pass
    def __add__(self, x: 'array') -> 'array': pass
    def __mul__(self, n: int) -> 'array': pass
    def __contains__(self, o: object) -> bool: pass
