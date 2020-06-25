import sys
from _typeshed import AnyPath
from typing import Any, Optional, Pattern

if sys.version_info < (3, 6):
    _SuccessType = bool
else:
    _SuccessType = int

if sys.version_info >= (3, 7):
    from py_compile import PycInvalidationMode

if sys.version_info >= (3, 9):
    def compile_dir(
        dir: AnyPath,
        maxlevels: Optional[int] = ...,
        ddir: Optional[AnyPath] = ...,
        force: bool = ...,
        rx: Optional[Pattern[Any]] = ...,
        quiet: int = ...,
        legacy: bool = ...,
        optimize: int = ...,
        workers: int = ...,
        invalidation_mode: Optional[PycInvalidationMode] = ...,
        *,
        stripdir: Optional[str] = ...,  # TODO: change to Optional[AnyPath] once https://bugs.python.org/issue40447 is resolved
        prependdir: Optional[AnyPath] = ...,
        limit_sl_dest: Optional[AnyPath] = ...,
    ) -> _SuccessType: ...
    def compile_file(
        fullname: AnyPath,
        ddir: Optional[AnyPath] = ...,
        force: bool = ...,
        rx: Optional[Pattern[Any]] = ...,
        quiet: int = ...,
        legacy: bool = ...,
        optimize: int = ...,
        invalidation_mode: Optional[PycInvalidationMode] = ...,
        *,
        stripdir: Optional[str] = ...,  # TODO: change to Optional[AnyPath] once https://bugs.python.org/issue40447 is resolved
        prependdir: Optional[AnyPath] = ...,
        limit_sl_dest: Optional[AnyPath] = ...,
    ) -> _SuccessType: ...
elif sys.version_info >= (3, 7):
    def compile_dir(
        dir: AnyPath,
        maxlevels: int = ...,
        ddir: Optional[AnyPath] = ...,
        force: bool = ...,
        rx: Optional[Pattern[Any]] = ...,
        quiet: int = ...,
        legacy: bool = ...,
        optimize: int = ...,
        workers: int = ...,
        invalidation_mode: Optional[PycInvalidationMode] = ...,
    ) -> _SuccessType: ...
    def compile_file(
        fullname: AnyPath,
        ddir: Optional[AnyPath] = ...,
        force: bool = ...,
        rx: Optional[Pattern[Any]] = ...,
        quiet: int = ...,
        legacy: bool = ...,
        optimize: int = ...,
        invalidation_mode: Optional[PycInvalidationMode] = ...,
    ) -> _SuccessType: ...

else:
    # rx can be any object with a 'search' method; once we have Protocols we can change the type
    def compile_dir(
        dir: AnyPath,
        maxlevels: int = ...,
        ddir: Optional[AnyPath] = ...,
        force: bool = ...,
        rx: Optional[Pattern[Any]] = ...,
        quiet: int = ...,
        legacy: bool = ...,
        optimize: int = ...,
        workers: int = ...,
    ) -> _SuccessType: ...
    def compile_file(
        fullname: AnyPath,
        ddir: Optional[AnyPath] = ...,
        force: bool = ...,
        rx: Optional[Pattern[Any]] = ...,
        quiet: int = ...,
        legacy: bool = ...,
        optimize: int = ...,
    ) -> _SuccessType: ...

if sys.version_info >= (3, 7):
    def compile_path(
        skip_curdir: bool = ...,
        maxlevels: int = ...,
        force: bool = ...,
        quiet: int = ...,
        legacy: bool = ...,
        optimize: int = ...,
        invalidation_mode: Optional[PycInvalidationMode] = ...,
    ) -> _SuccessType: ...
else:
    def compile_path(
        skip_curdir: bool = ...,
        maxlevels: int = ...,
        force: bool = ...,
        quiet: int = ...,
        legacy: bool = ...,
        optimize: int = ...,
    ) -> _SuccessType: ...
