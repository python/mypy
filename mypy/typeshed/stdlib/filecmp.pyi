import sys
from _typeshed import StrOrBytesPath
from os import PathLike
from typing import Any, AnyStr, Callable, Generic, Iterable, Sequence
from typing_extensions import Literal

if sys.version_info >= (3, 9):
    from types import GenericAlias

__all__ = ["clear_cache", "cmp", "dircmp", "cmpfiles", "DEFAULT_IGNORES"]

DEFAULT_IGNORES: list[str]
BUFSIZE: Literal[8192]

def cmp(f1: StrOrBytesPath, f2: StrOrBytesPath, shallow: int | bool = ...) -> bool: ...
def cmpfiles(
    a: AnyStr | PathLike[AnyStr],
    b: AnyStr | PathLike[AnyStr],
    common: Iterable[AnyStr | PathLike[AnyStr]],
    shallow: int | bool = ...,
) -> tuple[list[AnyStr], list[AnyStr], list[AnyStr]]: ...

class dircmp(Generic[AnyStr]):
    def __init__(
        self,
        a: AnyStr | PathLike[AnyStr],
        b: AnyStr | PathLike[AnyStr],
        ignore: Sequence[AnyStr] | None = ...,
        hide: Sequence[AnyStr] | None = ...,
    ) -> None: ...
    left: AnyStr
    right: AnyStr
    hide: Sequence[AnyStr]
    ignore: Sequence[AnyStr]
    # These properties are created at runtime by __getattr__
    subdirs: dict[AnyStr, dircmp[AnyStr]]
    same_files: list[AnyStr]
    diff_files: list[AnyStr]
    funny_files: list[AnyStr]
    common_dirs: list[AnyStr]
    common_files: list[AnyStr]
    common_funny: list[AnyStr]
    common: list[AnyStr]
    left_only: list[AnyStr]
    right_only: list[AnyStr]
    left_list: list[AnyStr]
    right_list: list[AnyStr]
    def report(self) -> None: ...
    def report_partial_closure(self) -> None: ...
    def report_full_closure(self) -> None: ...
    methodmap: dict[str, Callable[[], None]]
    def phase0(self) -> None: ...
    def phase1(self) -> None: ...
    def phase2(self) -> None: ...
    def phase3(self) -> None: ...
    def phase4(self) -> None: ...
    def phase4_closure(self) -> None: ...
    if sys.version_info >= (3, 9):
        def __class_getitem__(cls, item: Any) -> GenericAlias: ...

def clear_cache() -> None: ...
