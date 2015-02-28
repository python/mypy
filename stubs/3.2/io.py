# Stubs for io

# Based on http://docs.python.org/3.2/library/io.html

# Only a subset of functionality is included (see below).
# TODO IOBase
# TODO RawIOBase
# TODO BufferedIOBase
# TODO FileIO
# TODO BufferedReader
# TODO BufferedWriter
# TODO BufferedRandom
# TODO BufferedRWPair
# TODO TextIOBase
# TODO IncrementalNewlineDecoder

DEFAULT_BUFFER_SIZE = 0

from typing import List, BinaryIO, TextIO, IO, overload, Iterator, Iterable, Undefined, Any
import _io
from _io import (
    BlockingIOError, open
)

open = open
BlockingIOError = BlockingIOError

class UnsupportedOperation(ValueError, OSError): pass

class FileIO(_io._RawIOBase):
    _finalizing = Undefined(Any)
    closed = Undefined(Any)
    closefd = Undefined(Any)
    mode = Undefined(Any)
    def __init__(self, name, mode=Undefined, closefd=Undefined, opener=Undefined): pass
    def _dealloc_warn(self, *args, **kwargs): pass
    def close(self): pass
    def fileno(self): pass
    def isatty(self): pass
    def read(self, *args, **kwargs): pass
    def readable(self): pass
    def readall(self): pass
    def readinto(self): pass
    def seek(self, *args, **kwargs): pass
    def seekable(self): pass
    def tell(self): pass
    def truncate(self, *args, **kwargs): pass
    def writable(self): pass
    def write(self, *args, **kwargs): pass
    def __getstate__(self): pass

class BufferedReader(_io._BufferedIOBase):
    _finalizing = Undefined(Any)
    closed = Undefined(Any)
    mode = Undefined(Any)
    name = Undefined(Any)
    raw = Undefined(Any)
    def __init__(self, raw, buffer_size=Undefined): pass
    def _dealloc_warn(self, *args, **kwargs): pass
    def close(self, *args, **kwargs): pass
    def detach(self, *args, **kwargs): pass
    def fileno(self): pass
    def flush(self, *args, **kwargs): pass
    def isatty(self, *args, **kwargs): pass
    def peek(self, *args, **kwargs): pass
    def read(self, *args, **kwargs): pass
    def read1(self, *args, **kwargs): pass
    def readable(self): pass
    def readinto(self, b): pass
    def readline(self, *args, **kwargs): pass
    def seek(self, *args, **kwargs): pass
    def seekable(self): pass
    def tell(self): pass
    def truncate(self, *args, **kwargs): pass
    def writable(self): pass
    def __getstate__(self): pass
    def __next__(self): pass
    def __sizeof__(self): pass

class BufferedWriter(_io._BufferedIOBase):
    _finalizing = Undefined(Any)
    closed = Undefined(Any)
    mode = Undefined(Any)
    name = Undefined(Any)
    raw = Undefined(Any)
    def __init__(self, raw, buffer_size=Undefined): pass
    def _dealloc_warn(self, *args, **kwargs): pass
    def close(self, *args, **kwargs): pass
    def detach(self, *args, **kwargs): pass
    def fileno(self): pass
    def flush(self, *args, **kwargs): pass
    def isatty(self, *args, **kwargs): pass
    def readable(self): pass
    def seek(self, *args, **kwargs): pass
    def seekable(self): pass
    def tell(self): pass
    def truncate(self, *args, **kwargs): pass
    def writable(self): pass
    def write(self, *args, **kwargs): pass
    def __getstate__(self): pass
    def __sizeof__(self): pass

class BufferedRWPair(_io._BufferedIOBase):
    closed = Undefined(Any)
    def __init__(self, reader, writer, buffer_size=Undefined): pass
    def close(self, *args, **kwargs): pass
    def flush(self, *args, **kwargs): pass
    def isatty(self, *args, **kwargs): pass
    def peek(self, *args, **kwargs): pass
    def read(self, *args, **kwargs): pass
    def read1(self, *args, **kwargs): pass
    def readable(self): pass
    def readinto(self, b): pass
    def writable(self): pass
    def write(self, *args, **kwargs): pass
    def __getstate__(self): pass

class BufferedRandom(_io._BufferedIOBase):
    _finalizing = Undefined(Any)
    closed = Undefined(Any)
    mode = Undefined(Any)
    name = Undefined(Any)
    raw = Undefined(Any)
    def __init__(self, raw, buffer_size=Undefined): pass
    def _dealloc_warn(self, *args, **kwargs): pass
    def close(self, *args, **kwargs): pass
    def detach(self, *args, **kwargs): pass
    def fileno(self): pass
    def flush(self, *args, **kwargs): pass
    def isatty(self, *args, **kwargs): pass
    def peek(self, *args, **kwargs): pass
    def read(self, *args, **kwargs): pass
    def read1(self, *args, **kwargs): pass
    def readable(self): pass
    def readinto(self, b): pass
    def readline(self, *args, **kwargs): pass
    def seek(self, *args, **kwargs): pass
    def seekable(self): pass
    def tell(self): pass
    def truncate(self, *args, **kwargs): pass
    def writable(self): pass
    def write(self, *args, **kwargs): pass
    def __getstate__(self): pass
    def __next__(self): pass
    def __sizeof__(self): pass

SEEK_SET = Undefined(Any)
SEEK_CUR = Undefined(Any)
SEEK_END = Undefined(Any)

class IOBase(_io._IOBase): pass
class RawIOBase(_io._RawIOBase, IOBase): pass
class BufferedIOBase(_io._BufferedIOBase, IOBase): pass
class TextIOBase(_io._TextIOBase, IOBase): pass

class BytesIO(BinaryIO):
    def __init__(self, initial_bytes: bytes = b'') -> None: pass
    # TODO getbuffer
    # TODO see comments in BinaryIO for missing functionality
    def close(self) -> None: pass
    def closed(self) -> bool: pass
    def fileno(self) -> int: pass
    def flush(self) -> None: pass
    def isatty(self) -> bool: pass
    def read(self, n: int = -1) -> bytes: pass
    def readable(self) -> bool: pass
    def readline(self, limit: int = -1) -> bytes: pass
    def readlines(self, hint: int = -1) -> List[bytes]: pass
    def seek(self, offset: int, whence: int = 0) -> int: pass
    def seekable(self) -> bool: pass
    def tell(self) -> int: pass
    def truncate(self, size: int = None) -> int: pass
    def writable(self) -> bool: pass
    @overload
    def write(self, s: bytes) -> int: pass
    @overload
    def write(self, s: bytearray) -> int: pass
    def writelines(self, lines: Iterable[bytes]) -> None: pass
    def getvalue(self) -> bytes: pass
    def read1(self) -> str: pass

    def __iter__(self) -> Iterator[bytes]: pass
    def __enter__(self) -> 'BytesIO': pass
    def __exit__(self, type, value, traceback) -> bool: pass

class StringIO(TextIO):
    def __init__(self, initial_value: str = '',
                 newline: str = None) -> None: pass
    # TODO see comments in BinaryIO for missing functionality
    def close(self) -> None: pass
    def closed(self) -> bool: pass
    def fileno(self) -> int: pass
    def flush(self) -> None: pass
    def isatty(self) -> bool: pass
    def read(self, n: int = -1) -> str: pass
    def readable(self) -> bool: pass
    def readline(self, limit: int = -1) -> str: pass
    def readlines(self, hint: int = -1) -> List[str]: pass
    def seek(self, offset: int, whence: int = 0) -> int: pass
    def seekable(self) -> bool: pass
    def tell(self) -> int: pass
    def truncate(self, size: int = None) -> int: pass
    def writable(self) -> bool: pass
    def write(self, s: str) -> int: pass
    def writelines(self, lines: Iterable[str]) -> None: pass
    def getvalue(self) -> str: pass

    def __iter__(self) -> Iterator[str]: pass
    def __enter__(self) -> 'StringIO': pass
    def __exit__(self, type, value, traceback) -> bool: pass

class TextIOWrapper(TextIO):
    # write_through is undocumented but used by subprocess
    def __init__(self, buffer: IO[bytes], encoding: str = None,
                 errors: str = None, newline: str = None,
                 line_buffering: bool = False,
                 write_through: bool = True) -> None: pass
    # TODO see comments in BinaryIO for missing functionality
    def close(self) -> None: pass
    def closed(self) -> bool: pass
    def fileno(self) -> int: pass
    def flush(self) -> None: pass
    def isatty(self) -> bool: pass
    def read(self, n: int = -1) -> str: pass
    def readable(self) -> bool: pass
    def readline(self, limit: int = -1) -> str: pass
    def readlines(self, hint: int = -1) -> List[str]: pass
    def seek(self, offset: int, whence: int = 0) -> int: pass
    def seekable(self) -> bool: pass
    def tell(self) -> int: pass
    def truncate(self, size: int = None) -> int: pass
    def writable(self) -> bool: pass
    def write(self, s: str) -> int: pass
    def writelines(self, lines: Iterable[str]) -> None: pass

    def __iter__(self) -> Iterator[str]: pass
    def __enter__(self) -> StringIO: pass
    def __exit__(self, type, value, traceback) -> bool: pass
