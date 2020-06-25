# Utility types for typeshed

# This module contains various common types to be used by typeshed. The
# module and its types do not exist at runtime. You can use this module
# outside of typeshed, but no API stability guarantees are made. To use
# it in implementation (.py) files, the following construct must be used:
#
#     from typing import TYPE_CHECKING
#     if TYPE_CHECKING:
#         from _typeshed import ...
#
# If on Python versions < 3.10 and "from __future__ import annotations"
# is not used, types from this module must be quoted.

import array
import mmap
import sys
from typing import Protocol, Text, TypeVar, Union
from typing_extensions import Literal

_T_co = TypeVar("_T_co", covariant=True)
_T_contra = TypeVar("_T_contra", contravariant=True)

# StrPath and AnyPath can be used in places where a
# path can be used instead of a string, starting with Python 3.6.
if sys.version_info >= (3, 6):
    from os import PathLike
    StrPath = Union[str, PathLike[str]]
    BytesPath = Union[bytes, PathLike[bytes]]
    AnyPath = Union[str, bytes, PathLike[str], PathLike[bytes]]
else:
    StrPath = Text
    BytesPath = bytes
    AnyPath = Union[Text, bytes]

OpenTextMode = Literal[
    'r', 'r+', '+r', 'rt', 'tr', 'rt+', 'r+t', '+rt', 'tr+', 't+r', '+tr',
    'w', 'w+', '+w', 'wt', 'tw', 'wt+', 'w+t', '+wt', 'tw+', 't+w', '+tw',
    'a', 'a+', '+a', 'at', 'ta', 'at+', 'a+t', '+at', 'ta+', 't+a', '+ta',
    'x', 'x+', '+x', 'xt', 'tx', 'xt+', 'x+t', '+xt', 'tx+', 't+x', '+tx',
    'U', 'rU', 'Ur', 'rtU', 'rUt', 'Urt', 'trU', 'tUr', 'Utr',
]
OpenBinaryModeUpdating = Literal[
    'rb+', 'r+b', '+rb', 'br+', 'b+r', '+br',
    'wb+', 'w+b', '+wb', 'bw+', 'b+w', '+bw',
    'ab+', 'a+b', '+ab', 'ba+', 'b+a', '+ba',
    'xb+', 'x+b', '+xb', 'bx+', 'b+x', '+bx',
]
OpenBinaryModeWriting = Literal[
    'wb', 'bw',
    'ab', 'ba',
    'xb', 'bx',
]
OpenBinaryModeReading = Literal[
    'rb', 'br',
    'rbU', 'rUb', 'Urb', 'brU', 'bUr', 'Ubr',
]
OpenBinaryMode = Union[OpenBinaryModeUpdating, OpenBinaryModeReading, OpenBinaryModeWriting]

class HasFileno(Protocol):
    def fileno(self) -> int: ...

FileDescriptor = int
FileDescriptorLike = Union[int, HasFileno]

class SupportsRead(Protocol[_T_co]):
    def read(self, __length: int = ...) -> _T_co: ...
class SupportsReadline(Protocol[_T_co]):
    def readline(self, __length: int = ...) -> _T_co: ...
class SupportsWrite(Protocol[_T_contra]):
    def write(self, __s: _T_contra) -> int: ...

if sys.version_info >= (3,):
    ReadableBuffer = Union[bytes, bytearray, memoryview, array.array, mmap.mmap]
    WriteableBuffer = Union[bytearray, memoryview, array.array, mmap.mmap]
else:
    ReadableBuffer = Union[bytes, bytearray, memoryview, array.array, mmap.mmap, buffer]
    WriteableBuffer = Union[bytearray, memoryview, array.array, mmap.mmap, buffer]
