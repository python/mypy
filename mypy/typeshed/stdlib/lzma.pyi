import io
from _typeshed import ReadableBuffer, Self, StrOrBytesPath
from typing import IO, Any, Mapping, Sequence, TextIO, overload
from typing_extensions import Literal, final

__all__ = [
    "CHECK_NONE",
    "CHECK_CRC32",
    "CHECK_CRC64",
    "CHECK_SHA256",
    "CHECK_ID_MAX",
    "CHECK_UNKNOWN",
    "FILTER_LZMA1",
    "FILTER_LZMA2",
    "FILTER_DELTA",
    "FILTER_X86",
    "FILTER_IA64",
    "FILTER_ARM",
    "FILTER_ARMTHUMB",
    "FILTER_POWERPC",
    "FILTER_SPARC",
    "FORMAT_AUTO",
    "FORMAT_XZ",
    "FORMAT_ALONE",
    "FORMAT_RAW",
    "MF_HC3",
    "MF_HC4",
    "MF_BT2",
    "MF_BT3",
    "MF_BT4",
    "MODE_FAST",
    "MODE_NORMAL",
    "PRESET_DEFAULT",
    "PRESET_EXTREME",
    "LZMACompressor",
    "LZMADecompressor",
    "LZMAFile",
    "LZMAError",
    "open",
    "compress",
    "decompress",
    "is_check_supported",
]

_OpenBinaryWritingMode = Literal["w", "wb", "x", "xb", "a", "ab"]
_OpenTextWritingMode = Literal["wt", "xt", "at"]

_PathOrFile = StrOrBytesPath | IO[bytes]

_FilterChain = Sequence[Mapping[str, Any]]

FORMAT_AUTO: Literal[0]
FORMAT_XZ: Literal[1]
FORMAT_ALONE: Literal[2]
FORMAT_RAW: Literal[3]
CHECK_NONE: Literal[0]
CHECK_CRC32: Literal[1]
CHECK_CRC64: Literal[4]
CHECK_SHA256: Literal[10]
CHECK_ID_MAX: Literal[15]
CHECK_UNKNOWN: Literal[16]
FILTER_LZMA1: int  # v big number
FILTER_LZMA2: Literal[33]
FILTER_DELTA: Literal[3]
FILTER_X86: Literal[4]
FILTER_IA64: Literal[6]
FILTER_ARM: Literal[7]
FILTER_ARMTHUMB: Literal[8]
FILTER_SPARC: Literal[9]
FILTER_POWERPC: Literal[5]
MF_HC3: Literal[3]
MF_HC4: Literal[4]
MF_BT2: Literal[18]
MF_BT3: Literal[19]
MF_BT4: Literal[20]
MODE_FAST: Literal[1]
MODE_NORMAL: Literal[2]
PRESET_DEFAULT: Literal[6]
PRESET_EXTREME: int  # v big number

# from _lzma.c
@final
class LZMADecompressor:
    def __init__(self, format: int | None = ..., memlimit: int | None = ..., filters: _FilterChain | None = ...) -> None: ...
    def decompress(self, data: bytes, max_length: int = ...) -> bytes: ...
    @property
    def check(self) -> int: ...
    @property
    def eof(self) -> bool: ...
    @property
    def unused_data(self) -> bytes: ...
    @property
    def needs_input(self) -> bool: ...

# from _lzma.c
@final
class LZMACompressor:
    def __init__(
        self, format: int | None = ..., check: int = ..., preset: int | None = ..., filters: _FilterChain | None = ...
    ) -> None: ...
    def compress(self, __data: bytes) -> bytes: ...
    def flush(self) -> bytes: ...

class LZMAError(Exception): ...

class LZMAFile(io.BufferedIOBase, IO[bytes]):
    def __init__(
        self,
        filename: _PathOrFile | None = ...,
        mode: str = ...,
        *,
        format: int | None = ...,
        check: int = ...,
        preset: int | None = ...,
        filters: _FilterChain | None = ...,
    ) -> None: ...
    def __enter__(self: Self) -> Self: ...
    def close(self) -> None: ...
    @property
    def closed(self) -> bool: ...
    def fileno(self) -> int: ...
    def seekable(self) -> bool: ...
    def readable(self) -> bool: ...
    def writable(self) -> bool: ...
    def peek(self, size: int = ...) -> bytes: ...
    def read(self, size: int | None = ...) -> bytes: ...
    def read1(self, size: int = ...) -> bytes: ...
    def readline(self, size: int | None = ...) -> bytes: ...
    def write(self, data: ReadableBuffer) -> int: ...
    def seek(self, offset: int, whence: int = ...) -> int: ...
    def tell(self) -> int: ...

@overload
def open(
    filename: _PathOrFile,
    mode: Literal["r", "rb"] = ...,
    *,
    format: int | None = ...,
    check: Literal[-1] = ...,
    preset: None = ...,
    filters: _FilterChain | None = ...,
    encoding: None = ...,
    errors: None = ...,
    newline: None = ...,
) -> LZMAFile: ...
@overload
def open(
    filename: _PathOrFile,
    mode: _OpenBinaryWritingMode,
    *,
    format: int | None = ...,
    check: int = ...,
    preset: int | None = ...,
    filters: _FilterChain | None = ...,
    encoding: None = ...,
    errors: None = ...,
    newline: None = ...,
) -> LZMAFile: ...
@overload
def open(
    filename: StrOrBytesPath,
    mode: Literal["rt"],
    *,
    format: int | None = ...,
    check: Literal[-1] = ...,
    preset: None = ...,
    filters: _FilterChain | None = ...,
    encoding: str | None = ...,
    errors: str | None = ...,
    newline: str | None = ...,
) -> TextIO: ...
@overload
def open(
    filename: StrOrBytesPath,
    mode: _OpenTextWritingMode,
    *,
    format: int | None = ...,
    check: int = ...,
    preset: int | None = ...,
    filters: _FilterChain | None = ...,
    encoding: str | None = ...,
    errors: str | None = ...,
    newline: str | None = ...,
) -> TextIO: ...
@overload
def open(
    filename: _PathOrFile,
    mode: str,
    *,
    format: int | None = ...,
    check: int = ...,
    preset: int | None = ...,
    filters: _FilterChain | None = ...,
    encoding: str | None = ...,
    errors: str | None = ...,
    newline: str | None = ...,
) -> LZMAFile | TextIO: ...
def compress(
    data: bytes, format: int = ..., check: int = ..., preset: int | None = ..., filters: _FilterChain | None = ...
) -> bytes: ...
def decompress(data: bytes, format: int = ..., memlimit: int | None = ..., filters: _FilterChain | None = ...) -> bytes: ...
def is_check_supported(__check_id: int) -> bool: ...
