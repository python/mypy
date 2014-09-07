# Stubs for io

# Based on https://docs.python.org/2/library/io.html

# Only a subset of functionality is included.

DEFAULT_BUFFER_SIZE = 0

from typing import List, BinaryIO, TextIO, IO, overload, Iterator, Iterable, Any, Union

def open(file: Union[str, unicode, int],
         mode: unicode = 'r', buffering: int = -1, encoding: unicode = None,
         errors: unicode = None, newline: unicode = None,
         closefd: bool = True) -> IO[Any]: pass

class BytesIO(BinaryIO):
    def __init__(self, initial_bytes: str = b'') -> None: pass
    # TODO getbuffer
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
    @overload
    def write(self, s: str) -> int: pass
    @overload
    def write(self, s: bytearray) -> int: pass
    def writelines(self, lines: Iterable[str]) -> None: pass
    def getvalue(self) -> str: pass
    def read1(self) -> str: pass

    def __iter__(self) -> Iterator[str]: pass
    def __enter__(self) -> 'BytesIO': pass
    def __exit__(self, type, value, traceback) -> bool: pass

class StringIO(TextIO):
    def __init__(self, initial_value: unicode = '',
                 newline: unicode = None) -> None: pass
    # TODO see comments in BinaryIO for missing functionality
    def close(self) -> None: pass
    def closed(self) -> bool: pass
    def fileno(self) -> int: pass
    def flush(self) -> None: pass
    def isatty(self) -> bool: pass
    def read(self, n: int = -1) -> unicode: pass
    def readable(self) -> bool: pass
    def readline(self, limit: int = -1) -> unicode: pass
    def readlines(self, hint: int = -1) -> List[unicode]: pass
    def seek(self, offset: int, whence: int = 0) -> int: pass
    def seekable(self) -> bool: pass
    def tell(self) -> int: pass
    def truncate(self, size: int = None) -> int: pass
    def writable(self) -> bool: pass
    def write(self, s: unicode) -> int: pass
    def writelines(self, lines: Iterable[unicode]) -> None: pass
    def getvalue(self) -> unicode: pass

    def __iter__(self) -> Iterator[unicode]: pass
    def __enter__(self) -> 'StringIO': pass
    def __exit__(self, type, value, traceback) -> bool: pass

class TextIOWrapper(TextIO):
    # write_through is undocumented but used by subprocess
    def __init__(self, buffer: IO[str], encoding: unicode = None,
                 errors: unicode = None, newline: unicode = None,
                 line_buffering: bool = False,
                 write_through: bool = True) -> None: pass
    # TODO see comments in BinaryIO for missing functionality
    def close(self) -> None: pass
    def closed(self) -> bool: pass
    def fileno(self) -> int: pass
    def flush(self) -> None: pass
    def isatty(self) -> bool: pass
    def read(self, n: int = -1) -> unicode: pass
    def readable(self) -> bool: pass
    def readline(self, limit: int = -1) -> unicode: pass
    def readlines(self, hint: int = -1) -> List[unicode]: pass
    def seek(self, offset: int, whence: int = 0) -> int: pass
    def seekable(self) -> bool: pass
    def tell(self) -> int: pass
    def truncate(self, size: int = None) -> int: pass
    def writable(self) -> bool: pass
    def write(self, s: unicode) -> int: pass
    def writelines(self, lines: Iterable[unicode]) -> None: pass

    def __iter__(self) -> Iterator[unicode]: pass
    def __enter__(self) -> StringIO: pass
    def __exit__(self, type, value, traceback) -> bool: pass
