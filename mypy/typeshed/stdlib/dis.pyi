import sys
import types
from opcode import (
    EXTENDED_ARG as EXTENDED_ARG,
    HAVE_ARGUMENT as HAVE_ARGUMENT,
    cmp_op as cmp_op,
    hascompare as hascompare,
    hasconst as hasconst,
    hasfree as hasfree,
    hasjabs as hasjabs,
    hasjrel as hasjrel,
    haslocal as haslocal,
    hasname as hasname,
    hasnargs as hasnargs,
    opmap as opmap,
    opname as opname,
    stack_effect as stack_effect,
)
from typing import IO, Any, Callable, Iterator, NamedTuple, Union

# Strictly this should not have to include Callable, but mypy doesn't use FunctionType
# for functions (python/mypy#3171)
_HaveCodeType = Union[types.MethodType, types.FunctionType, types.CodeType, type, Callable[..., Any]]
_HaveCodeOrStringType = Union[_HaveCodeType, str, bytes]

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
    def __init__(self, x: _HaveCodeOrStringType, *, first_line: int | None = ..., current_offset: int | None = ...) -> None: ...
    def __iter__(self) -> Iterator[Instruction]: ...
    def __repr__(self) -> str: ...
    def info(self) -> str: ...
    def dis(self) -> str: ...
    @classmethod
    def from_traceback(cls, tb: types.TracebackType) -> Bytecode: ...

COMPILER_FLAG_NAMES: dict[int, str]

def findlabels(code: _HaveCodeType) -> list[int]: ...
def findlinestarts(code: _HaveCodeType) -> Iterator[tuple[int, int]]: ...
def pretty_flags(flags: int) -> str: ...
def code_info(x: _HaveCodeOrStringType) -> str: ...

if sys.version_info >= (3, 7):
    def dis(x: _HaveCodeOrStringType | None = ..., *, file: IO[str] | None = ..., depth: int | None = ...) -> None: ...

else:
    def dis(x: _HaveCodeOrStringType | None = ..., *, file: IO[str] | None = ...) -> None: ...

def distb(tb: types.TracebackType | None = ..., *, file: IO[str] | None = ...) -> None: ...
def disassemble(co: _HaveCodeType, lasti: int = ..., *, file: IO[str] | None = ...) -> None: ...
def disco(co: _HaveCodeType, lasti: int = ..., *, file: IO[str] | None = ...) -> None: ...
def show_code(co: _HaveCodeType, *, file: IO[str] | None = ...) -> None: ...
def get_instructions(x: _HaveCodeType, *, first_line: int | None = ...) -> Iterator[Instruction]: ...
