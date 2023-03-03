import sys
from ctypes import _CArgObject, _PointerLike
from typing_extensions import TypeAlias

FUNCFLAG_CDECL: int
FUNCFLAG_PYTHONAPI: int
FUNCFLAG_USE_ERRNO: int
FUNCFLAG_USE_LASTERROR: int
RTLD_GLOBAL: int
RTLD_LOCAL: int

if sys.version_info >= (3, 11):
    CTYPES_MAX_ARGCOUNT: int

if sys.platform == "win32":
    # Description, Source, HelpFile, HelpContext, scode
    _COMError_Details: TypeAlias = tuple[str | None, str | None, str | None, int | None, int | None]

    class COMError(Exception):
        hresult: int
        text: str | None
        details: _COMError_Details

        def __init__(self, hresult: int, text: str | None, details: _COMError_Details) -> None: ...

    def CopyComPointer(src: _PointerLike, dst: _PointerLike | _CArgObject) -> int: ...

    FUNCFLAG_HRESULT: int
    FUNCFLAG_STDCALL: int
