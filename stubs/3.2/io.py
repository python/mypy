# Stubs for io

# Based on http://docs.python.org/3.2/library/io.html

DEFAULT_BUFFER_SIZE = 0

from typing import List, BinaryIO, TextIO, IO, overload, Iterator, Iterable, Undefined, Any
import builtins
import codecs
import _io

DEFAULT_BUFFER_SIZE = Undefined(int)
SEEK_SET = Undefined(int)
SEEK_CUR = Undefined(int)
SEEK_END = Undefined(int)

open = builtins.open

class BlockingIOError(OSError): pass
class UnsupportedOperation(ValueError, OSError): pass

class IncrementalNewlineDecoder(codecs.IncrementalDecoder):
    newlines = Undefined(Any)
    def __init__(self, *args, **kwargs): pass
    def decode(self, input, final=False): pass
    def getstate(self): pass
    def reset(self): pass
    def setstate(self, state): pass

class IOBase(_io._IOBase): pass
class RawIOBase(_io._RawIOBase, IOBase): pass
class BufferedIOBase(_io._BufferedIOBase, IOBase): pass
class TextIOBase(_io._TextIOBase, IOBase): pass

class FileIO(_io._RawIOBase):
    closefd = Undefined(Any)
    mode = Undefined(Any)
    def __init__(self, name, mode=Undefined, closefd=Undefined, opener=Undefined): pass
    def readinto(self, b): pass
    def write(self, b): pass

class BufferedReader(_io._BufferedIOBase):
    mode = Undefined(Any)
    name = Undefined(Any)
    raw = Undefined(Any)
    def __init__(self, raw, buffer_size=Undefined): pass
    def peek(self, size: int = -1): pass

class BufferedWriter(_io._BufferedIOBase):
    mode = Undefined(Any)
    name = Undefined(Any)
    raw = Undefined(Any)
    def __init__(self, raw, buffer_size=Undefined): pass

class BufferedRWPair(_io._BufferedIOBase):
    def __init__(self, reader, writer, buffer_size=Undefined): pass
    def peek(self, size: int = -1): pass

class BufferedRandom(_io._BufferedIOBase):
    mode = Undefined(Any)
    name = Undefined(Any)
    raw = Undefined(Any)
    def __init__(self, raw, buffer_size=Undefined): pass
    def peek(self, size: int = -1): pass

class BytesIO(BinaryIO):
    def __init__(self, initial_bytes: bytes = b'') -> None: pass
    # TODO getbuffer
    # TODO see comments in BinaryIO for missing functionality
    def close(self) -> None: pass
    @property
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
    @property
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
    # TODO: This is actually a base class of _io._TextIOBase.
    # write_through is undocumented but used by subprocess
    def __init__(self, buffer: IO[bytes], encoding: str = None,
                 errors: str = None, newline: str = None,
                 line_buffering: bool = False,
                 write_through: bool = True) -> None: pass
    # TODO see comments in BinaryIO for missing functionality
    def close(self) -> None: pass
    @property
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
