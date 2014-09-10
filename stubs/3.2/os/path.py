# Stubs for os.path
# Ron Murawski <ron@horizonchess.com>

# based on http://docs.python.org/3.2/library/os.path.html

from typing import overload, List, Any, AnyStr, Tuple, BinaryIO, TextIO, Union

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
def abspath(path: Union[str, bytes]) -> str: pass
def basename(path: Union[str, bytes]) -> str: pass

# NOTE: Empty List[bytes] results in '' (str) => fall back to Any return type.
def commonprefix(list: List[AnyStr]) -> Any: pass
def dirname(path: Union[str, bytes]) -> str: pass
def exists(path: Union[str, bytes]) -> bool: pass
def lexists(path: Union[str, bytes]) -> bool: pass
def expanduser(path: Union[str, bytes]) -> str: pass
def expandvars(path: Union[str, bytes]) -> str: pass


# These return float if os.stat_float_times() == True
def getatime(path: Union[str, bytes]) -> Any: pass
def getmtime(path: Union[str, bytes]) -> Any: pass
def getctime(path: Union[str, bytes]) -> Any: pass

def getsize(path: Union[str, bytes]) -> int: pass
def isabs(path: Union[str, bytes]) -> bool: pass
def isfile(path: Union[str, bytes]) -> bool: pass
def isdir(path: Union[str, bytes]) -> bool: pass
def islink(path: Union[str, bytes]) -> bool: pass
def ismount(path: Union[str, bytes]) -> bool: pass

@overload
def join(path: str, *paths: str) -> str: pass
@overload
def join(path: bytes, *paths: bytes) -> bytes: pass

def normcase(path: Union[str, bytes]) -> str: pass
def normpath(path: Union[str, bytes]) -> str: pass
def realpath(path: Union[str, bytes]) -> str: pass
@overload
def relpath(path: str, start: str = None) -> str: pass
@overload
def relpath(path: bytes, start: bytes = None) -> bytes: pass
@overload
def samefile(path1: str, path2: str) -> bool: pass
@overload
def samefile(path1: bytes, path2: bytes) -> bool: pass
def sameopenfile(fp1: int, fp2: int) -> bool: pass
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
