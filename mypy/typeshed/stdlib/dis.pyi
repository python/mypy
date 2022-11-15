import sys
import types
from _typeshed import Self
from collections.abc import Callable, Iterator
from opcode import *  # `dis` re-exports it as a part of public API
from typing import IO, Any, NamedTuple
from typing_extensions import TypeAlias

__all__ = [
    "code_info",
    "dis",
    "disassemble",
    "distb",
    "disco",
    "findlinestarts",
    "findlabels",
    "show_code",
    "get_instructions",
    "Instruction",
    "Bytecode",
    "cmp_op",
    "hasconst",
    "hasname",
    "hasjrel",
    "hasjabs",
    "haslocal",
    "hascompare",
    "hasfree",
    "opname",
    "opmap",
    "HAVE_ARGUMENT",
    "EXTENDED_ARG",
    "hasnargs",
    "stack_effect",
]

# Strictly this should not have to include Callable, but mypy doesn't use FunctionType
# for functions (python/mypy#3171)
_HaveCodeType: TypeAlias = types.MethodType | types.FunctionType | types.CodeType | type | Callable[..., Any]

if sys.version_info >= (3, 11):
    class Positions(NamedTuple):
        lineno: int | None = ...
        end_lineno: int | None = ...
        col_offset: int | None = ...
        end_col_offset: int | None = ...

if sys.version_info >= (3, 11):
    class Instruction(NamedTuple):
        opname: str
        opcode: int
        arg: int | None
        argval: Any
        argrepr: str
        offset: int
        starts_line: int | None
        is_jump_target: bool
        positions: Positions | None = ...

else:
    class Instruction(NamedTuple):
        opname: str
        opcode: int
        arg: int | None
        argval: Any
        argrepr: str
        offset: int
        starts_line: int | None
        is_jump_target: bool

class Bytecode:
    codeobj: types.CodeType
    first_line: int
    if sys.version_info >= (3, 11):
        def __init__(
            self,
            x: _HaveCodeType | str,
            *,
            first_line: int | None = ...,
            current_offset: int | None = ...,
            show_caches: bool = ...,
            adaptive: bool = ...,
        ) -> None: ...
        @classmethod
        def from_traceback(
            cls: type[Self], tb: types.TracebackType, *, show_caches: bool = ..., adaptive: bool = ...
        ) -> Self: ...
    else:
        def __init__(self, x: _HaveCodeType | str, *, first_line: int | None = ..., current_offset: int | None = ...) -> None: ...
        @classmethod
        def from_traceback(cls: type[Self], tb: types.TracebackType) -> Self: ...

    def __iter__(self) -> Iterator[Instruction]: ...
    def info(self) -> str: ...
    def dis(self) -> str: ...

COMPILER_FLAG_NAMES: dict[int, str]

def findlabels(code: _HaveCodeType) -> list[int]: ...
def findlinestarts(code: _HaveCodeType) -> Iterator[tuple[int, int]]: ...
def pretty_flags(flags: int) -> str: ...
def code_info(x: _HaveCodeType | str) -> str: ...

if sys.version_info >= (3, 11):
    def dis(
        x: _HaveCodeType | str | bytes | bytearray | None = ...,
        *,
        file: IO[str] | None = ...,
        depth: int | None = ...,
        show_caches: bool = ...,
        adaptive: bool = ...,
    ) -> None: ...

else:
    def dis(
        x: _HaveCodeType | str | bytes | bytearray | None = ..., *, file: IO[str] | None = ..., depth: int | None = ...
    ) -> None: ...

if sys.version_info >= (3, 11):
    def disassemble(
        co: _HaveCodeType, lasti: int = ..., *, file: IO[str] | None = ..., show_caches: bool = ..., adaptive: bool = ...
    ) -> None: ...
    def disco(
        co: _HaveCodeType, lasti: int = ..., *, file: IO[str] | None = ..., show_caches: bool = ..., adaptive: bool = ...
    ) -> None: ...
    def distb(
        tb: types.TracebackType | None = ..., *, file: IO[str] | None = ..., show_caches: bool = ..., adaptive: bool = ...
    ) -> None: ...
    def get_instructions(
        x: _HaveCodeType, *, first_line: int | None = ..., show_caches: bool = ..., adaptive: bool = ...
    ) -> Iterator[Instruction]: ...

else:
    def disassemble(co: _HaveCodeType, lasti: int = ..., *, file: IO[str] | None = ...) -> None: ...
    def disco(co: _HaveCodeType, lasti: int = ..., *, file: IO[str] | None = ...) -> None: ...
    def distb(tb: types.TracebackType | None = ..., *, file: IO[str] | None = ...) -> None: ...
    def get_instructions(x: _HaveCodeType, *, first_line: int | None = ...) -> Iterator[Instruction]: ...

def show_code(co: _HaveCodeType, *, file: IO[str] | None = ...) -> None: ...
