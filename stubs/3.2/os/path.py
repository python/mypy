# Stubs for os.path
# Ron Murawski <ron@horizonchess.com>

# based on http://docs.python.org/3.2/library/os.path.html

from typing import overload, List, Any, AnyStr, Tuple, BinaryIO, TextIO

# ----- os.path variables -----
supports_unicode_filenames = False
# aliases (also in os)
curdir = ''
pardir = ''
sep = ''
altsep = ''
extsep = ''
pathsep = ''
defpath = ''
devnull = ''

# ----- os.path function stubs -----
@overload
def abspath(path: str) -> str: pass
@overload
def abspath(path: bytes) -> bytes: pass
@overload
def basename(path: str) -> str: pass
@overload
def basename(path: bytes) -> bytes: pass
# NOTE: Empty List[bytes] results in '' (str) => fall back to Any return type.
def commonprefix(list: List[AnyStr]) -> Any: pass
@overload
def dirname(path: str) -> str: pass
@overload
def dirname(path: bytes) -> bytes: pass
@overload
def exists(path: str) -> bool: pass
@overload
def exists(path: bytes) -> bool: pass
@overload
def lexists(path: str) -> bool: pass
@overload
def lexists(path: bytes) -> bool: pass
@overload
def expanduser(path: str) -> str: pass
@overload
def expanduser(path: bytes) -> bytes: pass
@overload
def expandvars(path: str) -> str: pass
@overload
def expandvars(path: bytes) -> bytes: pass

# These return float if os.stat_float_times() == True
@overload
def getatime(path: str) -> Any: pass
@overload
def getatime(path: bytes) -> Any: pass
@overload
def getmtime(path: str) -> Any: pass
@overload
def getmtime(path: bytes) -> Any: pass
@overload
def getctime(path: str) -> Any: pass
@overload
def getctime(path: bytes) -> Any: pass

@overload
def getsize(path: str) -> int: pass
@overload
def getsize(path: bytes) -> int: pass
@overload
def isabs(path: str) -> bool: pass
@overload
def isabs(path: bytes) -> bool: pass
@overload
def isfile(path: str) -> bool: pass
@overload
def isfile(path: bytes) -> bool: pass
@overload
def isdir(path: str) -> bool: pass
@overload
def isdir(path: bytes) -> bool: pass
@overload
def islink(path: str) -> bool: pass
@overload
def islink(path: bytes) -> bool: pass
@overload
def ismount(path: str) -> bool: pass
@overload
def ismount(path: bytes) -> bool: pass
@overload
def join(path: str, *paths: str) -> str: pass
@overload
def join(path: bytes, *paths: bytes) -> bytes: pass
@overload
def normcase(path: str) -> str: pass
@overload
def normcase(path: bytes) -> bytes: pass
@overload
def normpath(path: str) -> str: pass
@overload
def normpath(path: bytes) -> bytes: pass
@overload
def realpath(path: str) -> str: pass
@overload
def realpath(path: bytes) -> bytes: pass
@overload
def relpath(path: str, start: str = None) -> str: pass
@overload
def relpath(path: bytes, start: bytes = None) -> bytes: pass
@overload
def samefile(path1: str, path2: str) -> bool: pass
@overload
def samefile(path1: bytes, path2: bytes) -> bool: pass
@overload
def sameopenfile(fp1: BinaryIO, fp2: BinaryIO) -> bool: pass
@overload
def sameopenfile(fp1: TextIO, fp2: TextIO) -> bool: pass
#def samestat(stat1: stat_result,
#             stat2: stat_result) -> bool: pass  # Unix only
@overload
def split(path: str) -> Tuple[str, str]: pass
@overload
def split(path: bytes) -> Tuple[bytes, bytes]: pass
@overload
def splitdrive(path: str) -> Tuple[str, str]: pass
@overload
def splitdrive(path: bytes) -> Tuple[bytes, bytes]: pass
@overload
def splitext(path: str) -> Tuple[str, str]: pass
@overload
def splitext(path: bytes) -> Tuple[bytes, bytes]: pass
#def splitunc(path: str) -> Tuple[str, str]: pass  # Windows only, deprecated
