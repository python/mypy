# Stubs for types

# TODO this is work in progress

from typing import Any, Callable, Dict, Sequence

class ModuleType:
    __name__ = ... # type: str
    __file__ = ... # type: str
    def __init__(self, name: str, doc: Any) -> None: ...

class MethodType: ...
class BuiltinMethodType: ...

class CodeType:
    """Create a code object.  Not for the faint of heart."""
    def __init__(self,
            argcount: int,
            kwonlyargcount: int,
            nlocals: int,
            stacksize: int,
            flags: int,
            codestring: bytes,
            constants: Sequence[Any],
            names: Sequence[str],
            varnames: Sequence[str],
            filename: str,
            name: str,
            firstlineno: int,
            lnotab: bytes,
            freevars: Sequence[str] = (),
            cellvars: Sequence[str] = (),
    ) -> None:
        self.co_argcount = argcount
        self.co_kwonlyargcount = kwonlyargcount
        self.co_nlocals = nlocals
        self.co_stacksize = stacksize
        self.co_flags = flags
        self.co_code = codestring
        self.co_consts = constants
        self.co_names = names
        self.co_varnames = varnames
        self.co_filename = filename
        self.co_name = name
        self.co_firstlineno = firstlineno
        self.co_lnotab = lnotab
        self.co_freevars = freevars
        self.co_cellvars = cellvars

class FrameType:
    f_back = ... # type: FrameType
    f_builtins = ... # type: Dict[str, Any]
    f_code = ... # type: CodeType
    f_globals = ... # type: Dict[str, Any]
    f_lasti = ... # type: int
    f_lineno = ... # type: int
    f_locals = ... # type: Dict[str, Any]
    f_trace = ... # type: Callable[[], None]

    def clear(self) -> None: pass

class TracebackType:
    tb_frame = ... # type: FrameType
    tb_lasti = ... # type: int
    tb_lineno = ... # type: int
    tb_next = ... # type: TracebackType
