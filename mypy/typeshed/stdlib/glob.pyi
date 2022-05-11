import sys
from _typeshed import StrOrBytesPath
from collections.abc import Iterator
from typing import AnyStr

__all__ = ["escape", "glob", "iglob"]

def glob0(dirname: AnyStr, pattern: AnyStr) -> list[AnyStr]: ...
def glob1(dirname: AnyStr, pattern: AnyStr) -> list[AnyStr]: ...

if sys.version_info >= (3, 11):
    def glob(
        pathname: AnyStr,
        *,
        root_dir: StrOrBytesPath | None = ...,
        dir_fd: int | None = ...,
        recursive: bool = ...,
        include_hidden: bool = ...,
    ) -> list[AnyStr]: ...
    def iglob(
        pathname: AnyStr,
        *,
        root_dir: StrOrBytesPath | None = ...,
        dir_fd: int | None = ...,
        recursive: bool = ...,
        include_hidden: bool = ...,
    ) -> Iterator[AnyStr]: ...

elif sys.version_info >= (3, 10):
    def glob(
        pathname: AnyStr, *, root_dir: StrOrBytesPath | None = ..., dir_fd: int | None = ..., recursive: bool = ...
    ) -> list[AnyStr]: ...
    def iglob(
        pathname: AnyStr, *, root_dir: StrOrBytesPath | None = ..., dir_fd: int | None = ..., recursive: bool = ...
    ) -> Iterator[AnyStr]: ...

else:
    def glob(pathname: AnyStr, *, recursive: bool = ...) -> list[AnyStr]: ...
    def iglob(pathname: AnyStr, *, recursive: bool = ...) -> Iterator[AnyStr]: ...

def escape(pathname: AnyStr) -> AnyStr: ...
def has_magic(s: str | bytes) -> bool: ...  # undocumented
