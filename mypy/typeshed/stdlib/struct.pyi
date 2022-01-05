import sys
from _typeshed import ReadableBuffer, WriteableBuffer
from typing import Any, Iterator, Tuple

class error(Exception): ...

def pack(fmt: str | bytes, *v: Any) -> bytes: ...
def pack_into(fmt: str | bytes, buffer: WriteableBuffer, offset: int, *v: Any) -> None: ...
def unpack(__format: str | bytes, __buffer: ReadableBuffer) -> Tuple[Any, ...]: ...
def unpack_from(__format: str | bytes, buffer: ReadableBuffer, offset: int = ...) -> Tuple[Any, ...]: ...
def iter_unpack(__format: str | bytes, __buffer: ReadableBuffer) -> Iterator[Tuple[Any, ...]]: ...
def calcsize(__format: str | bytes) -> int: ...

class Struct:
    if sys.version_info >= (3, 7):
        format: str
    else:
        format: bytes
    size: int
    def __init__(self, format: str | bytes) -> None: ...
    def pack(self, *v: Any) -> bytes: ...
    def pack_into(self, buffer: WriteableBuffer, offset: int, *v: Any) -> None: ...
    def unpack(self, __buffer: ReadableBuffer) -> Tuple[Any, ...]: ...
    def unpack_from(self, buffer: ReadableBuffer, offset: int = ...) -> Tuple[Any, ...]: ...
    def iter_unpack(self, __buffer: ReadableBuffer) -> Iterator[Tuple[Any, ...]]: ...
