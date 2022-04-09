# Utility types for typeshed
#
# See the README.md file in this directory for more information.

import array
import ctypes
import mmap
import sys
from os import PathLike
from typing import AbstractSet, Any, Awaitable, Container, Generic, Iterable, Protocol, TypeVar
from typing_extensions import Final, Literal, TypeAlias, final

_KT = TypeVar("_KT")
_KT_co = TypeVar("_KT_co", covariant=True)
_KT_contra = TypeVar("_KT_contra", contravariant=True)
_VT = TypeVar("_VT")
_VT_co = TypeVar("_VT_co", covariant=True)
_T = TypeVar("_T")
_T_co = TypeVar("_T_co", covariant=True)
_T_contra = TypeVar("_T_contra", contravariant=True)

# Use for "self" annotations:
#   def __enter__(self: Self) -> Self: ...
Self = TypeVar("Self")  # noqa: Y001

# For partially known annotations. Usually, fields where type annotations
# haven't been added are left unannotated, but in some situations this
# isn't possible or a type is already partially known. In cases like these,
# use Incomplete instead of Any as a marker. For example, use
# "Incomplete | None" instead of "Any | None".
Incomplete: TypeAlias = Any

# stable
class IdentityFunction(Protocol):
    def __call__(self, __x: _T) -> _T: ...

# stable
class SupportsNext(Protocol[_T_co]):
    def __next__(self) -> _T_co: ...

# stable
class SupportsAnext(Protocol[_T_co]):
    def __anext__(self) -> Awaitable[_T_co]: ...

# Comparison protocols

class SupportsDunderLT(Protocol):
    def __lt__(self, __other: Any) -> bool: ...

class SupportsDunderGT(Protocol):
    def __gt__(self, __other: Any) -> bool: ...

class SupportsDunderLE(Protocol):
    def __le__(self, __other: Any) -> bool: ...

class SupportsDunderGE(Protocol):
    def __ge__(self, __other: Any) -> bool: ...

class SupportsAllComparisons(SupportsDunderLT, SupportsDunderGT, SupportsDunderLE, SupportsDunderGE, Protocol): ...

SupportsRichComparison: TypeAlias = SupportsDunderLT | SupportsDunderGT
SupportsRichComparisonT = TypeVar("SupportsRichComparisonT", bound=SupportsRichComparison)  # noqa: Y001

class SupportsDivMod(Protocol[_T_contra, _T_co]):
    def __divmod__(self, __other: _T_contra) -> _T_co: ...

class SupportsRDivMod(Protocol[_T_contra, _T_co]):
    def __rdivmod__(self, __other: _T_contra) -> _T_co: ...

class SupportsLenAndGetItem(Protocol[_T_co]):
    def __len__(self) -> int: ...
    def __getitem__(self, __k: int) -> _T_co: ...

class SupportsTrunc(Protocol):
    def __trunc__(self) -> int: ...

# Mapping-like protocols

# stable
class SupportsItems(Protocol[_KT_co, _VT_co]):
    def items(self) -> AbstractSet[tuple[_KT_co, _VT_co]]: ...

# stable
class SupportsKeysAndGetItem(Protocol[_KT, _VT_co]):
    def keys(self) -> Iterable[_KT]: ...
    def __getitem__(self, __k: _KT) -> _VT_co: ...

# stable
class SupportsGetItem(Container[_KT_contra], Protocol[_KT_contra, _VT_co]):
    def __getitem__(self, __k: _KT_contra) -> _VT_co: ...

# stable
class SupportsItemAccess(SupportsGetItem[_KT_contra, _VT], Protocol[_KT_contra, _VT]):
    def __setitem__(self, __k: _KT_contra, __v: _VT) -> None: ...
    def __delitem__(self, __v: _KT_contra) -> None: ...

# These aliases are simple strings in Python 2.
StrPath: TypeAlias = str | PathLike[str]  # stable
BytesPath: TypeAlias = bytes | PathLike[bytes]  # stable
StrOrBytesPath: TypeAlias = str | bytes | PathLike[str] | PathLike[bytes]  # stable

OpenTextModeUpdating = Literal[
    "r+",
    "+r",
    "rt+",
    "r+t",
    "+rt",
    "tr+",
    "t+r",
    "+tr",
    "w+",
    "+w",
    "wt+",
    "w+t",
    "+wt",
    "tw+",
    "t+w",
    "+tw",
    "a+",
    "+a",
    "at+",
    "a+t",
    "+at",
    "ta+",
    "t+a",
    "+ta",
    "x+",
    "+x",
    "xt+",
    "x+t",
    "+xt",
    "tx+",
    "t+x",
    "+tx",
]
OpenTextModeWriting: TypeAlias = Literal["w", "wt", "tw", "a", "at", "ta", "x", "xt", "tx"]
OpenTextModeReading: TypeAlias = Literal["r", "rt", "tr", "U", "rU", "Ur", "rtU", "rUt", "Urt", "trU", "tUr", "Utr"]
OpenTextMode: TypeAlias = OpenTextModeUpdating | OpenTextModeWriting | OpenTextModeReading
OpenBinaryModeUpdating: TypeAlias = Literal[
    "rb+",
    "r+b",
    "+rb",
    "br+",
    "b+r",
    "+br",
    "wb+",
    "w+b",
    "+wb",
    "bw+",
    "b+w",
    "+bw",
    "ab+",
    "a+b",
    "+ab",
    "ba+",
    "b+a",
    "+ba",
    "xb+",
    "x+b",
    "+xb",
    "bx+",
    "b+x",
    "+bx",
]
OpenBinaryModeWriting: TypeAlias = Literal["wb", "bw", "ab", "ba", "xb", "bx"]
OpenBinaryModeReading: TypeAlias = Literal["rb", "br", "rbU", "rUb", "Urb", "brU", "bUr", "Ubr"]
OpenBinaryMode: TypeAlias = OpenBinaryModeUpdating | OpenBinaryModeReading | OpenBinaryModeWriting

# stable
class HasFileno(Protocol):
    def fileno(self) -> int: ...

FileDescriptor: TypeAlias = int  # stable
FileDescriptorLike: TypeAlias = int | HasFileno  # stable

# stable
class SupportsRead(Protocol[_T_co]):
    def read(self, __length: int = ...) -> _T_co: ...

# stable
class SupportsReadline(Protocol[_T_co]):
    def readline(self, __length: int = ...) -> _T_co: ...

# stable
class SupportsNoArgReadline(Protocol[_T_co]):
    def readline(self) -> _T_co: ...

# stable
class SupportsWrite(Protocol[_T_contra]):
    def write(self, __s: _T_contra) -> object: ...

ReadOnlyBuffer: TypeAlias = bytes  # stable
# Anything that implements the read-write buffer interface.
# The buffer interface is defined purely on the C level, so we cannot define a normal Protocol
# for it. Instead we have to list the most common stdlib buffer classes in a Union.
WriteableBuffer: TypeAlias = bytearray | memoryview | array.array[Any] | mmap.mmap | ctypes._CData  # stable
# Same as _WriteableBuffer, but also includes read-only buffer types (like bytes).
ReadableBuffer: TypeAlias = ReadOnlyBuffer | WriteableBuffer  # stable

# stable
if sys.version_info >= (3, 10):
    from types import NoneType as NoneType
else:
    # Used by type checkers for checks involving None (does not exist at runtime)
    @final
    class NoneType:
        def __bool__(self) -> Literal[False]: ...

# This is an internal CPython type that is like, but subtly different from, a NamedTuple
# Subclasses of this type are found in multiple modules.
# In typeshed, `structseq` is only ever used as a mixin in combination with a fixed-length `Tuple`
# See discussion at #6546 & #6560
# `structseq` classes are unsubclassable, so are all decorated with `@final`.
class structseq(Generic[_T_co]):
    n_fields: Final[int]
    n_unnamed_fields: Final[int]
    n_sequence_fields: Final[int]
    # The first parameter will generally only take an iterable of a specific length.
    # E.g. `os.uname_result` takes any iterable of length exactly 5.
    #
    # The second parameter will accept a dict of any kind without raising an exception,
    # but only has any meaning if you supply it a dict where the keys are strings.
    # https://github.com/python/typeshed/pull/6560#discussion_r767149830
    def __new__(cls: type[Self], sequence: Iterable[_T_co], dict: dict[str, Any] = ...) -> Self: ...
