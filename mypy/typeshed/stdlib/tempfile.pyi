import io
import sys
from _typeshed import BytesPath, GenericPath, Self, StrPath, WriteableBuffer
from collections.abc import Iterable, Iterator
from types import TracebackType
from typing import IO, Any, AnyStr, Generic, overload
from typing_extensions import Literal, TypeAlias

if sys.version_info >= (3, 9):
    from types import GenericAlias

__all__ = [
    "NamedTemporaryFile",
    "TemporaryFile",
    "SpooledTemporaryFile",
    "TemporaryDirectory",
    "mkstemp",
    "mkdtemp",
    "mktemp",
    "TMP_MAX",
    "gettempprefix",
    "tempdir",
    "gettempdir",
    "gettempprefixb",
    "gettempdirb",
]

# global variables
TMP_MAX: int
tempdir: str | None
template: str

_StrMode: TypeAlias = Literal["r", "w", "a", "x", "r+", "w+", "a+", "x+", "rt", "wt", "at", "xt", "r+t", "w+t", "a+t", "x+t"]
_BytesMode: TypeAlias = Literal["rb", "wb", "ab", "xb", "r+b", "w+b", "a+b", "x+b"]

if sys.version_info >= (3, 8):
    @overload
    def NamedTemporaryFile(
        mode: _StrMode,
        buffering: int = ...,
        encoding: str | None = ...,
        newline: str | None = ...,
        suffix: AnyStr | None = ...,
        prefix: AnyStr | None = ...,
        dir: GenericPath[AnyStr] | None = ...,
        delete: bool = ...,
        *,
        errors: str | None = ...,
    ) -> _TemporaryFileWrapper[str]: ...
    @overload
    def NamedTemporaryFile(
        mode: _BytesMode = ...,
        buffering: int = ...,
        encoding: str | None = ...,
        newline: str | None = ...,
        suffix: AnyStr | None = ...,
        prefix: AnyStr | None = ...,
        dir: GenericPath[AnyStr] | None = ...,
        delete: bool = ...,
        *,
        errors: str | None = ...,
    ) -> _TemporaryFileWrapper[bytes]: ...
    @overload
    def NamedTemporaryFile(
        mode: str = ...,
        buffering: int = ...,
        encoding: str | None = ...,
        newline: str | None = ...,
        suffix: AnyStr | None = ...,
        prefix: AnyStr | None = ...,
        dir: GenericPath[AnyStr] | None = ...,
        delete: bool = ...,
        *,
        errors: str | None = ...,
    ) -> _TemporaryFileWrapper[Any]: ...

else:
    @overload
    def NamedTemporaryFile(
        mode: _StrMode,
        buffering: int = ...,
        encoding: str | None = ...,
        newline: str | None = ...,
        suffix: AnyStr | None = ...,
        prefix: AnyStr | None = ...,
        dir: GenericPath[AnyStr] | None = ...,
        delete: bool = ...,
    ) -> _TemporaryFileWrapper[str]: ...
    @overload
    def NamedTemporaryFile(
        mode: _BytesMode = ...,
        buffering: int = ...,
        encoding: str | None = ...,
        newline: str | None = ...,
        suffix: AnyStr | None = ...,
        prefix: AnyStr | None = ...,
        dir: GenericPath[AnyStr] | None = ...,
        delete: bool = ...,
    ) -> _TemporaryFileWrapper[bytes]: ...
    @overload
    def NamedTemporaryFile(
        mode: str = ...,
        buffering: int = ...,
        encoding: str | None = ...,
        newline: str | None = ...,
        suffix: AnyStr | None = ...,
        prefix: AnyStr | None = ...,
        dir: GenericPath[AnyStr] | None = ...,
        delete: bool = ...,
    ) -> _TemporaryFileWrapper[Any]: ...

if sys.platform == "win32":
    TemporaryFile = NamedTemporaryFile
else:
    if sys.version_info >= (3, 8):
        @overload
        def TemporaryFile(
            mode: _StrMode,
            buffering: int = ...,
            encoding: str | None = ...,
            newline: str | None = ...,
            suffix: AnyStr | None = ...,
            prefix: AnyStr | None = ...,
            dir: GenericPath[AnyStr] | None = ...,
            *,
            errors: str | None = ...,
        ) -> IO[str]: ...
        @overload
        def TemporaryFile(
            mode: _BytesMode = ...,
            buffering: int = ...,
            encoding: str | None = ...,
            newline: str | None = ...,
            suffix: AnyStr | None = ...,
            prefix: AnyStr | None = ...,
            dir: GenericPath[AnyStr] | None = ...,
            *,
            errors: str | None = ...,
        ) -> IO[bytes]: ...
        @overload
        def TemporaryFile(
            mode: str = ...,
            buffering: int = ...,
            encoding: str | None = ...,
            newline: str | None = ...,
            suffix: AnyStr | None = ...,
            prefix: AnyStr | None = ...,
            dir: GenericPath[AnyStr] | None = ...,
            *,
            errors: str | None = ...,
        ) -> IO[Any]: ...
    else:
        @overload
        def TemporaryFile(
            mode: _StrMode,
            buffering: int = ...,
            encoding: str | None = ...,
            newline: str | None = ...,
            suffix: AnyStr | None = ...,
            prefix: AnyStr | None = ...,
            dir: GenericPath[AnyStr] | None = ...,
        ) -> IO[str]: ...
        @overload
        def TemporaryFile(
            mode: _BytesMode = ...,
            buffering: int = ...,
            encoding: str | None = ...,
            newline: str | None = ...,
            suffix: AnyStr | None = ...,
            prefix: AnyStr | None = ...,
            dir: GenericPath[AnyStr] | None = ...,
        ) -> IO[bytes]: ...
        @overload
        def TemporaryFile(
            mode: str = ...,
            buffering: int = ...,
            encoding: str | None = ...,
            newline: str | None = ...,
            suffix: AnyStr | None = ...,
            prefix: AnyStr | None = ...,
            dir: GenericPath[AnyStr] | None = ...,
        ) -> IO[Any]: ...

class _TemporaryFileWrapper(Generic[AnyStr], IO[AnyStr]):
    file: IO[AnyStr]  # io.TextIOWrapper, io.BufferedReader or io.BufferedWriter
    name: str
    delete: bool
    def __init__(self, file: IO[AnyStr], name: str, delete: bool = ...) -> None: ...
    def __enter__(self: Self) -> Self: ...
    def __exit__(self, exc: type[BaseException] | None, value: BaseException | None, tb: TracebackType | None) -> None: ...
    def __getattr__(self, name: str) -> Any: ...
    def close(self) -> None: ...
    # These methods don't exist directly on this object, but
    # are delegated to the underlying IO object through __getattr__.
    # We need to add them here so that this class is concrete.
    def __iter__(self) -> Iterator[AnyStr]: ...
    # FIXME: __next__ doesn't actually exist on this class and should be removed:
    #        see also https://github.com/python/typeshed/pull/5456#discussion_r633068648
    # >>> import tempfile
    # >>> ntf=tempfile.NamedTemporaryFile()
    # >>> next(ntf)
    # Traceback (most recent call last):
    #   File "<stdin>", line 1, in <module>
    # TypeError: '_TemporaryFileWrapper' object is not an iterator
    def __next__(self) -> AnyStr: ...
    def fileno(self) -> int: ...
    def flush(self) -> None: ...
    def isatty(self) -> bool: ...
    def read(self, n: int = ...) -> AnyStr: ...
    def readable(self) -> bool: ...
    def readline(self, limit: int = ...) -> AnyStr: ...
    def readlines(self, hint: int = ...) -> list[AnyStr]: ...
    def seek(self, offset: int, whence: int = ...) -> int: ...
    def seekable(self) -> bool: ...
    def tell(self) -> int: ...
    def truncate(self, size: int | None = ...) -> int: ...
    def writable(self) -> bool: ...
    def write(self, s: AnyStr) -> int: ...
    def writelines(self, lines: Iterable[AnyStr]) -> None: ...

if sys.version_info >= (3, 11):
    _SpooledTemporaryFileBase = io.IOBase
else:
    _SpooledTemporaryFileBase = object

# It does not actually derive from IO[AnyStr], but it does mostly behave
# like one.
class SpooledTemporaryFile(IO[AnyStr], _SpooledTemporaryFileBase):
    @property
    def encoding(self) -> str: ...  # undocumented
    @property
    def newlines(self) -> str | tuple[str, ...] | None: ...  # undocumented
    # bytes needs to go first, as default mode is to open as bytes
    if sys.version_info >= (3, 8):
        @overload
        def __init__(
            self: SpooledTemporaryFile[bytes],
            max_size: int = ...,
            mode: _BytesMode = ...,
            buffering: int = ...,
            encoding: str | None = ...,
            newline: str | None = ...,
            suffix: str | None = ...,
            prefix: str | None = ...,
            dir: str | None = ...,
            *,
            errors: str | None = ...,
        ) -> None: ...
        @overload
        def __init__(
            self: SpooledTemporaryFile[str],
            max_size: int = ...,
            mode: _StrMode = ...,
            buffering: int = ...,
            encoding: str | None = ...,
            newline: str | None = ...,
            suffix: str | None = ...,
            prefix: str | None = ...,
            dir: str | None = ...,
            *,
            errors: str | None = ...,
        ) -> None: ...
        @overload
        def __init__(
            self,
            max_size: int = ...,
            mode: str = ...,
            buffering: int = ...,
            encoding: str | None = ...,
            newline: str | None = ...,
            suffix: str | None = ...,
            prefix: str | None = ...,
            dir: str | None = ...,
            *,
            errors: str | None = ...,
        ) -> None: ...
        @property
        def errors(self) -> str | None: ...
    else:
        @overload
        def __init__(
            self: SpooledTemporaryFile[bytes],
            max_size: int = ...,
            mode: _BytesMode = ...,
            buffering: int = ...,
            encoding: str | None = ...,
            newline: str | None = ...,
            suffix: str | None = ...,
            prefix: str | None = ...,
            dir: str | None = ...,
        ) -> None: ...
        @overload
        def __init__(
            self: SpooledTemporaryFile[str],
            max_size: int = ...,
            mode: _StrMode = ...,
            buffering: int = ...,
            encoding: str | None = ...,
            newline: str | None = ...,
            suffix: str | None = ...,
            prefix: str | None = ...,
            dir: str | None = ...,
        ) -> None: ...
        @overload
        def __init__(
            self,
            max_size: int = ...,
            mode: str = ...,
            buffering: int = ...,
            encoding: str | None = ...,
            newline: str | None = ...,
            suffix: str | None = ...,
            prefix: str | None = ...,
            dir: str | None = ...,
        ) -> None: ...

    def rollover(self) -> None: ...
    def __enter__(self: Self) -> Self: ...
    def __exit__(self, exc: type[BaseException] | None, value: BaseException | None, tb: TracebackType | None) -> None: ...
    # These methods are copied from the abstract methods of IO, because
    # SpooledTemporaryFile implements IO.
    # See also https://github.com/python/typeshed/pull/2452#issuecomment-420657918.
    def close(self) -> None: ...
    def fileno(self) -> int: ...
    def flush(self) -> None: ...
    def isatty(self) -> bool: ...
    if sys.version_info >= (3, 11):
        # These three work only if the SpooledTemporaryFile is opened in binary mode,
        # because the underlying object in text mode does not have these methods.
        def read1(self, __size: int = ...) -> AnyStr: ...
        def readinto(self, b: WriteableBuffer) -> int: ...
        def readinto1(self, b: WriteableBuffer) -> int: ...
        def detach(self) -> io.RawIOBase: ...

    def read(self, __n: int = ...) -> AnyStr: ...
    def readline(self, __limit: int | None = ...) -> AnyStr: ...  # type: ignore[override]
    def readlines(self, __hint: int = ...) -> list[AnyStr]: ...  # type: ignore[override]
    def seek(self, offset: int, whence: int = ...) -> int: ...
    def tell(self) -> int: ...
    def truncate(self, size: int | None = ...) -> None: ...  # type: ignore[override]
    def write(self, s: AnyStr) -> int: ...
    def writelines(self, iterable: Iterable[AnyStr]) -> None: ...  # type: ignore[override]
    def __iter__(self) -> Iterator[AnyStr]: ...  # type: ignore[override]
    # These exist at runtime only on 3.11+.
    def readable(self) -> bool: ...
    def seekable(self) -> bool: ...
    def writable(self) -> bool: ...
    def __next__(self) -> AnyStr: ...  # type: ignore[override]
    if sys.version_info >= (3, 9):
        def __class_getitem__(cls, item: Any) -> GenericAlias: ...

class TemporaryDirectory(Generic[AnyStr]):
    name: AnyStr
    if sys.version_info >= (3, 10):
        @overload
        def __init__(
            self: TemporaryDirectory[str],
            suffix: str | None = ...,
            prefix: str | None = ...,
            dir: StrPath | None = ...,
            ignore_cleanup_errors: bool = ...,
        ) -> None: ...
        @overload
        def __init__(
            self: TemporaryDirectory[bytes],
            suffix: bytes | None = ...,
            prefix: bytes | None = ...,
            dir: BytesPath | None = ...,
            ignore_cleanup_errors: bool = ...,
        ) -> None: ...
    else:
        @overload
        def __init__(
            self: TemporaryDirectory[str], suffix: str | None = ..., prefix: str | None = ..., dir: StrPath | None = ...
        ) -> None: ...
        @overload
        def __init__(
            self: TemporaryDirectory[bytes], suffix: bytes | None = ..., prefix: bytes | None = ..., dir: BytesPath | None = ...
        ) -> None: ...

    def cleanup(self) -> None: ...
    def __enter__(self) -> AnyStr: ...
    def __exit__(self, exc: type[BaseException] | None, value: BaseException | None, tb: TracebackType | None) -> None: ...
    if sys.version_info >= (3, 9):
        def __class_getitem__(cls, item: Any) -> GenericAlias: ...

# The overloads overlap, but they should still work fine.
@overload
def mkstemp(  # type: ignore[misc]
    suffix: str | None = ..., prefix: str | None = ..., dir: StrPath | None = ..., text: bool = ...
) -> tuple[int, str]: ...
@overload
def mkstemp(
    suffix: bytes | None = ..., prefix: bytes | None = ..., dir: BytesPath | None = ..., text: bool = ...
) -> tuple[int, bytes]: ...

# The overloads overlap, but they should still work fine.
@overload
def mkdtemp(suffix: str | None = ..., prefix: str | None = ..., dir: StrPath | None = ...) -> str: ...  # type: ignore[misc]
@overload
def mkdtemp(suffix: bytes | None = ..., prefix: bytes | None = ..., dir: BytesPath | None = ...) -> bytes: ...
def mktemp(suffix: str = ..., prefix: str = ..., dir: StrPath | None = ...) -> str: ...
def gettempdirb() -> bytes: ...
def gettempprefixb() -> bytes: ...
def gettempdir() -> str: ...
def gettempprefix() -> str: ...
