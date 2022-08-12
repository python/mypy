import os
import sys
from _typeshed import BytesPath, StrOrBytesPath, StrPath, SupportsRead, SupportsWrite
from collections.abc import Callable, Iterable, Sequence
from typing import Any, AnyStr, NamedTuple, TypeVar, overload
from typing_extensions import TypeAlias

__all__ = [
    "copyfileobj",
    "copyfile",
    "copymode",
    "copystat",
    "copy",
    "copy2",
    "copytree",
    "move",
    "rmtree",
    "Error",
    "SpecialFileError",
    "ExecError",
    "make_archive",
    "get_archive_formats",
    "register_archive_format",
    "unregister_archive_format",
    "get_unpack_formats",
    "register_unpack_format",
    "unregister_unpack_format",
    "unpack_archive",
    "ignore_patterns",
    "chown",
    "which",
    "get_terminal_size",
    "SameFileError",
    "disk_usage",
]

_StrOrBytesPathT = TypeVar("_StrOrBytesPathT", bound=StrOrBytesPath)
_StrPathT = TypeVar("_StrPathT", bound=StrPath)
# Return value of some functions that may either return a path-like object that was passed in or
# a string
_PathReturn: TypeAlias = Any

class Error(OSError): ...
class SameFileError(Error): ...
class SpecialFileError(OSError): ...
class ExecError(OSError): ...
class ReadError(OSError): ...
class RegistryError(Exception): ...

def copyfileobj(fsrc: SupportsRead[AnyStr], fdst: SupportsWrite[AnyStr], length: int = ...) -> None: ...
def copyfile(src: StrOrBytesPath, dst: _StrOrBytesPathT, *, follow_symlinks: bool = ...) -> _StrOrBytesPathT: ...
def copymode(src: StrOrBytesPath, dst: StrOrBytesPath, *, follow_symlinks: bool = ...) -> None: ...
def copystat(src: StrOrBytesPath, dst: StrOrBytesPath, *, follow_symlinks: bool = ...) -> None: ...
@overload
def copy(src: StrPath, dst: StrPath, *, follow_symlinks: bool = ...) -> _PathReturn: ...
@overload
def copy(src: BytesPath, dst: BytesPath, *, follow_symlinks: bool = ...) -> _PathReturn: ...
@overload
def copy2(src: StrPath, dst: StrPath, *, follow_symlinks: bool = ...) -> _PathReturn: ...
@overload
def copy2(src: BytesPath, dst: BytesPath, *, follow_symlinks: bool = ...) -> _PathReturn: ...
def ignore_patterns(*patterns: StrPath) -> Callable[[Any, list[str]], set[str]]: ...

if sys.version_info >= (3, 8):
    def copytree(
        src: StrPath,
        dst: StrPath,
        symlinks: bool = ...,
        ignore: None | Callable[[str, list[str]], Iterable[str]] | Callable[[StrPath, list[str]], Iterable[str]] = ...,
        copy_function: Callable[[str, str], object] = ...,
        ignore_dangling_symlinks: bool = ...,
        dirs_exist_ok: bool = ...,
    ) -> _PathReturn: ...

else:
    def copytree(
        src: StrPath,
        dst: StrPath,
        symlinks: bool = ...,
        ignore: None | Callable[[str, list[str]], Iterable[str]] | Callable[[StrPath, list[str]], Iterable[str]] = ...,
        copy_function: Callable[[str, str], object] = ...,
        ignore_dangling_symlinks: bool = ...,
    ) -> _PathReturn: ...

_OnErrorCallback: TypeAlias = Callable[[Callable[..., Any], Any, Any], object]

if sys.version_info >= (3, 11):
    def rmtree(
        path: StrOrBytesPath, ignore_errors: bool = ..., onerror: _OnErrorCallback | None = ..., *, dir_fd: int | None = ...
    ) -> None: ...

else:
    def rmtree(path: StrOrBytesPath, ignore_errors: bool = ..., onerror: _OnErrorCallback | None = ...) -> None: ...

_CopyFn: TypeAlias = Callable[[str, str], object] | Callable[[StrPath, StrPath], object]

# N.B. shutil.move appears to take bytes arguments, however,
# this does not work when dst is (or is within) an existing directory.
# (#6832)
if sys.version_info >= (3, 9):
    def move(src: StrPath, dst: StrPath, copy_function: _CopyFn = ...) -> _PathReturn: ...

else:
    # See https://bugs.python.org/issue32689
    def move(src: str, dst: StrPath, copy_function: _CopyFn = ...) -> _PathReturn: ...

class _ntuple_diskusage(NamedTuple):
    total: int
    used: int
    free: int

def disk_usage(path: int | StrOrBytesPath) -> _ntuple_diskusage: ...

# While chown can be imported on Windows, it doesn't actually work;
# see https://bugs.python.org/issue33140. We keep it here because it's
# in __all__.
@overload
def chown(path: StrOrBytesPath, user: str | int, group: None = ...) -> None: ...
@overload
def chown(path: StrOrBytesPath, user: None = ..., *, group: str | int) -> None: ...
@overload
def chown(path: StrOrBytesPath, user: None, group: str | int) -> None: ...
@overload
def chown(path: StrOrBytesPath, user: str | int, group: str | int) -> None: ...

if sys.version_info >= (3, 8):
    @overload
    def which(cmd: _StrPathT, mode: int = ..., path: StrPath | None = ...) -> str | _StrPathT | None: ...
    @overload
    def which(cmd: bytes, mode: int = ..., path: StrPath | None = ...) -> bytes | None: ...

else:
    def which(cmd: _StrPathT, mode: int = ..., path: StrPath | None = ...) -> str | _StrPathT | None: ...

def make_archive(
    base_name: str,
    format: str,
    root_dir: StrPath | None = ...,
    base_dir: StrPath | None = ...,
    verbose: bool = ...,
    dry_run: bool = ...,
    owner: str | None = ...,
    group: str | None = ...,
    logger: Any | None = ...,
) -> str: ...
def get_archive_formats() -> list[tuple[str, str]]: ...
@overload
def register_archive_format(
    name: str, function: Callable[..., object], extra_args: Sequence[tuple[str, Any] | list[Any]], description: str = ...
) -> None: ...
@overload
def register_archive_format(
    name: str, function: Callable[[str, str], object], extra_args: None = ..., description: str = ...
) -> None: ...
def unregister_archive_format(name: str) -> None: ...
def unpack_archive(filename: StrPath, extract_dir: StrPath | None = ..., format: str | None = ...) -> None: ...
@overload
def register_unpack_format(
    name: str,
    extensions: list[str],
    function: Callable[..., object],
    extra_args: Sequence[tuple[str, Any]],
    description: str = ...,
) -> None: ...
@overload
def register_unpack_format(
    name: str, extensions: list[str], function: Callable[[str, str], object], extra_args: None = ..., description: str = ...
) -> None: ...
def unregister_unpack_format(name: str) -> None: ...
def get_unpack_formats() -> list[tuple[str, list[str], str]]: ...
def get_terminal_size(fallback: tuple[int, int] = ...) -> os.terminal_size: ...
