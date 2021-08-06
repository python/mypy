import _compression
import sys
from _compression import BaseStream
from _typeshed import ReadableBuffer, Self, StrOrBytesPath, WriteableBuffer
from typing import IO, Any, Iterable, List, Optional, Protocol, TextIO, TypeVar, Union, overload
from typing_extensions import Literal, SupportsIndex

# The following attributes and methods are optional:
# def fileno(self) -> int: ...
# def close(self) -> object: ...
class _ReadableFileobj(_compression._Reader, Protocol): ...

class _WritableFileobj(Protocol):
    def write(self, __b: bytes) -> object: ...
    # The following attributes and methods are optional:
    # def fileno(self) -> int: ...
    # def close(self) -> object: ...

_T = TypeVar("_T")

def compress(data: bytes, compresslevel: int = ...) -> bytes: ...
def decompress(data: bytes) -> bytes: ...

_ReadBinaryMode = Literal["", "r", "rb"]
_WriteBinaryMode = Literal["w", "wb", "x", "xb", "a", "ab"]
_ReadTextMode = Literal["rt"]
_WriteTextMode = Literal["wt", "xt", "at"]

@overload
def open(
    filename: _ReadableFileobj,
    mode: _ReadBinaryMode = ...,
    compresslevel: int = ...,
    encoding: None = ...,
    errors: None = ...,
    newline: None = ...,
) -> BZ2File: ...
@overload
def open(
    filename: _ReadableFileobj,
    mode: _ReadTextMode,
    compresslevel: int = ...,
    encoding: Optional[str] = ...,
    errors: Optional[str] = ...,
    newline: Optional[str] = ...,
) -> TextIO: ...
@overload
def open(
    filename: _WritableFileobj,
    mode: _WriteBinaryMode,
    compresslevel: int = ...,
    encoding: None = ...,
    errors: None = ...,
    newline: None = ...,
) -> BZ2File: ...
@overload
def open(
    filename: _WritableFileobj,
    mode: _WriteTextMode,
    compresslevel: int = ...,
    encoding: Optional[str] = ...,
    errors: Optional[str] = ...,
    newline: Optional[str] = ...,
) -> TextIO: ...
@overload
def open(
    filename: StrOrBytesPath,
    mode: Union[_ReadBinaryMode, _WriteBinaryMode] = ...,
    compresslevel: int = ...,
    encoding: None = ...,
    errors: None = ...,
    newline: None = ...,
) -> BZ2File: ...
@overload
def open(
    filename: StrOrBytesPath,
    mode: Union[_ReadTextMode, _WriteTextMode],
    compresslevel: int = ...,
    encoding: Optional[str] = ...,
    errors: Optional[str] = ...,
    newline: Optional[str] = ...,
) -> TextIO: ...

class BZ2File(BaseStream, IO[bytes]):
    def __enter__(self: Self) -> Self: ...
    if sys.version_info >= (3, 9):
        @overload
        def __init__(self, filename: _WritableFileobj, mode: _WriteBinaryMode, *, compresslevel: int = ...) -> None: ...
        @overload
        def __init__(self, filename: _ReadableFileobj, mode: _ReadBinaryMode = ..., *, compresslevel: int = ...) -> None: ...
        @overload
        def __init__(
            self, filename: StrOrBytesPath, mode: Union[_ReadBinaryMode, _WriteBinaryMode] = ..., *, compresslevel: int = ...
        ) -> None: ...
    else:
        @overload
        def __init__(
            self, filename: _WritableFileobj, mode: _WriteBinaryMode, buffering: Optional[Any] = ..., compresslevel: int = ...
        ) -> None: ...
        @overload
        def __init__(
            self,
            filename: _ReadableFileobj,
            mode: _ReadBinaryMode = ...,
            buffering: Optional[Any] = ...,
            compresslevel: int = ...,
        ) -> None: ...
        @overload
        def __init__(
            self,
            filename: StrOrBytesPath,
            mode: Union[_ReadBinaryMode, _WriteBinaryMode] = ...,
            buffering: Optional[Any] = ...,
            compresslevel: int = ...,
        ) -> None: ...
    def read(self, size: Optional[int] = ...) -> bytes: ...
    def read1(self, size: int = ...) -> bytes: ...
    def readline(self, size: SupportsIndex = ...) -> bytes: ...  # type: ignore
    def readinto(self, b: WriteableBuffer) -> int: ...
    def readlines(self, size: SupportsIndex = ...) -> List[bytes]: ...
    def seek(self, offset: int, whence: int = ...) -> int: ...
    def write(self, data: ReadableBuffer) -> int: ...
    def writelines(self, seq: Iterable[ReadableBuffer]) -> None: ...

class BZ2Compressor(object):
    def __init__(self, compresslevel: int = ...) -> None: ...
    def compress(self, __data: bytes) -> bytes: ...
    def flush(self) -> bytes: ...

class BZ2Decompressor(object):
    def decompress(self, data: bytes, max_length: int = ...) -> bytes: ...
    @property
    def eof(self) -> bool: ...
    @property
    def needs_input(self) -> bool: ...
    @property
    def unused_data(self) -> bytes: ...
