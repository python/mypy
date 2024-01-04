from ctypes import (
    Array,
    Structure,
    _CField,
    _Pointer,
    _SimpleCData,
    c_byte,
    c_char,
    c_char_p,
    c_double,
    c_float,
    c_int,
    c_long,
    c_longlong,
    c_short,
    c_uint,
    c_ulong,
    c_ulonglong,
    c_ushort,
    c_void_p,
    c_wchar,
    c_wchar_p,
)
from typing import TypeVar
from typing_extensions import TypeAlias

BYTE = c_byte
WORD = c_ushort
DWORD = c_ulong
CHAR = c_char
WCHAR = c_wchar
UINT = c_uint
INT = c_int
DOUBLE = c_double
FLOAT = c_float
BOOLEAN = BYTE
BOOL = c_long

class VARIANT_BOOL(_SimpleCData[bool]): ...

ULONG = c_ulong
LONG = c_long
USHORT = c_ushort
SHORT = c_short
LARGE_INTEGER = c_longlong
_LARGE_INTEGER = c_longlong
ULARGE_INTEGER = c_ulonglong
_ULARGE_INTEGER = c_ulonglong

OLESTR = c_wchar_p
LPOLESTR = c_wchar_p
LPCOLESTR = c_wchar_p
LPWSTR = c_wchar_p
LPCWSTR = c_wchar_p
LPSTR = c_char_p
LPCSTR = c_char_p
LPVOID = c_void_p
LPCVOID = c_void_p

# These two types are pointer-sized unsigned and signed ints, respectively.
# At runtime, they are either c_[u]long or c_[u]longlong, depending on the host's pointer size
# (they are not really separate classes).
class WPARAM(_SimpleCData[int]): ...
class LPARAM(_SimpleCData[int]): ...

ATOM = WORD
LANGID = WORD
COLORREF = DWORD
LGRPID = DWORD
LCTYPE = DWORD
LCID = DWORD

HANDLE = c_void_p
HACCEL = HANDLE
HBITMAP = HANDLE
HBRUSH = HANDLE
HCOLORSPACE = HANDLE
HDC = HANDLE
HDESK = HANDLE
HDWP = HANDLE
HENHMETAFILE = HANDLE
HFONT = HANDLE
HGDIOBJ = HANDLE
HGLOBAL = HANDLE
HHOOK = HANDLE
HICON = HANDLE
HINSTANCE = HANDLE
HKEY = HANDLE
HKL = HANDLE
HLOCAL = HANDLE
HMENU = HANDLE
HMETAFILE = HANDLE
HMODULE = HANDLE
HMONITOR = HANDLE
HPALETTE = HANDLE
HPEN = HANDLE
HRGN = HANDLE
HRSRC = HANDLE
HSTR = HANDLE
HTASK = HANDLE
HWINSTA = HANDLE
HWND = HANDLE
SC_HANDLE = HANDLE
SERVICE_STATUS_HANDLE = HANDLE

_CIntLikeT = TypeVar("_CIntLikeT", bound=_SimpleCData[int])
_CIntLikeField: TypeAlias = _CField[_CIntLikeT, int, _CIntLikeT | int]

class RECT(Structure):
    left: _CIntLikeField[LONG]
    top: _CIntLikeField[LONG]
    right: _CIntLikeField[LONG]
    bottom: _CIntLikeField[LONG]

RECTL = RECT
_RECTL = RECT
tagRECT = RECT

class _SMALL_RECT(Structure):
    Left: _CIntLikeField[SHORT]
    Top: _CIntLikeField[SHORT]
    Right: _CIntLikeField[SHORT]
    Bottom: _CIntLikeField[SHORT]

SMALL_RECT = _SMALL_RECT

class _COORD(Structure):
    X: _CIntLikeField[SHORT]
    Y: _CIntLikeField[SHORT]

class POINT(Structure):
    x: _CIntLikeField[LONG]
    y: _CIntLikeField[LONG]

POINTL = POINT
_POINTL = POINT
tagPOINT = POINT

class SIZE(Structure):
    cx: _CIntLikeField[LONG]
    cy: _CIntLikeField[LONG]

SIZEL = SIZE
tagSIZE = SIZE

def RGB(red: int, green: int, blue: int) -> int: ...

class FILETIME(Structure):
    dwLowDateTime: _CIntLikeField[DWORD]
    dwHighDateTime: _CIntLikeField[DWORD]

_FILETIME = FILETIME

class MSG(Structure):
    hWnd: _CField[HWND, int | None, HWND | int | None]
    message: _CIntLikeField[UINT]
    wParam: _CIntLikeField[WPARAM]
    lParam: _CIntLikeField[LPARAM]
    time: _CIntLikeField[DWORD]
    pt: _CField[POINT, POINT, POINT]

tagMSG = MSG
MAX_PATH: int

class WIN32_FIND_DATAA(Structure):
    dwFileAttributes: _CIntLikeField[DWORD]
    ftCreationTime: _CField[FILETIME, FILETIME, FILETIME]
    ftLastAccessTime: _CField[FILETIME, FILETIME, FILETIME]
    ftLastWriteTime: _CField[FILETIME, FILETIME, FILETIME]
    nFileSizeHigh: _CIntLikeField[DWORD]
    nFileSizeLow: _CIntLikeField[DWORD]
    dwReserved0: _CIntLikeField[DWORD]
    dwReserved1: _CIntLikeField[DWORD]
    cFileName: _CField[Array[CHAR], bytes, bytes]
    cAlternateFileName: _CField[Array[CHAR], bytes, bytes]

class WIN32_FIND_DATAW(Structure):
    dwFileAttributes: _CIntLikeField[DWORD]
    ftCreationTime: _CField[FILETIME, FILETIME, FILETIME]
    ftLastAccessTime: _CField[FILETIME, FILETIME, FILETIME]
    ftLastWriteTime: _CField[FILETIME, FILETIME, FILETIME]
    nFileSizeHigh: _CIntLikeField[DWORD]
    nFileSizeLow: _CIntLikeField[DWORD]
    dwReserved0: _CIntLikeField[DWORD]
    dwReserved1: _CIntLikeField[DWORD]
    cFileName: _CField[Array[WCHAR], str, str]
    cAlternateFileName: _CField[Array[WCHAR], str, str]

class PBOOL(_Pointer[BOOL]): ...
class LPBOOL(_Pointer[BOOL]): ...
class PBOOLEAN(_Pointer[BOOLEAN]): ...
class PBYTE(_Pointer[BYTE]): ...
class LPBYTE(_Pointer[BYTE]): ...
class PCHAR(_Pointer[CHAR]): ...
class LPCOLORREF(_Pointer[COLORREF]): ...
class PDWORD(_Pointer[DWORD]): ...
class LPDWORD(_Pointer[DWORD]): ...
class PFILETIME(_Pointer[FILETIME]): ...
class LPFILETIME(_Pointer[FILETIME]): ...
class PFLOAT(_Pointer[FLOAT]): ...
class PHANDLE(_Pointer[HANDLE]): ...
class LPHANDLE(_Pointer[HANDLE]): ...
class PHKEY(_Pointer[HKEY]): ...
class LPHKL(_Pointer[HKL]): ...
class PINT(_Pointer[INT]): ...
class LPINT(_Pointer[INT]): ...
class PLARGE_INTEGER(_Pointer[LARGE_INTEGER]): ...
class PLCID(_Pointer[LCID]): ...
class PLONG(_Pointer[LONG]): ...
class LPLONG(_Pointer[LONG]): ...
class PMSG(_Pointer[MSG]): ...
class LPMSG(_Pointer[MSG]): ...
class PPOINT(_Pointer[POINT]): ...
class LPPOINT(_Pointer[POINT]): ...
class PPOINTL(_Pointer[POINTL]): ...
class PRECT(_Pointer[RECT]): ...
class LPRECT(_Pointer[RECT]): ...
class PRECTL(_Pointer[RECTL]): ...
class LPRECTL(_Pointer[RECTL]): ...
class LPSC_HANDLE(_Pointer[SC_HANDLE]): ...
class PSHORT(_Pointer[SHORT]): ...
class PSIZE(_Pointer[SIZE]): ...
class LPSIZE(_Pointer[SIZE]): ...
class PSIZEL(_Pointer[SIZEL]): ...
class LPSIZEL(_Pointer[SIZEL]): ...
class PSMALL_RECT(_Pointer[SMALL_RECT]): ...
class PUINT(_Pointer[UINT]): ...
class LPUINT(_Pointer[UINT]): ...
class PULARGE_INTEGER(_Pointer[ULARGE_INTEGER]): ...
class PULONG(_Pointer[ULONG]): ...
class PUSHORT(_Pointer[USHORT]): ...
class PWCHAR(_Pointer[WCHAR]): ...
class PWIN32_FIND_DATAA(_Pointer[WIN32_FIND_DATAA]): ...
class LPWIN32_FIND_DATAA(_Pointer[WIN32_FIND_DATAA]): ...
class PWIN32_FIND_DATAW(_Pointer[WIN32_FIND_DATAW]): ...
class LPWIN32_FIND_DATAW(_Pointer[WIN32_FIND_DATAW]): ...
class PWORD(_Pointer[WORD]): ...
class LPWORD(_Pointer[WORD]): ...
