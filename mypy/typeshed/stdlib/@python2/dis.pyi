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
    opmap as opmap,
    opname as opname,
)
from typing import Any, Callable, Iterator

# Strictly this should not have to include Callable, but mypy doesn't use FunctionType
# for functions (python/mypy#3171)
_have_code = types.MethodType | types.FunctionType | types.CodeType | type | Callable[..., Any]
_have_code_or_string = _have_code | str | bytes

COMPILER_FLAG_NAMES: dict[int, str]

def findlabels(code: _have_code) -> list[int]: ...
def findlinestarts(code: _have_code) -> Iterator[tuple[int, int]]: ...
def dis(x: _have_code_or_string = ...) -> None: ...
def distb(tb: types.TracebackType = ...) -> None: ...
def disassemble(co: _have_code, lasti: int = ...) -> None: ...
def disco(co: _have_code, lasti: int = ...) -> None: ...
