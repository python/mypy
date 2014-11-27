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
def abspath(path: AnyStr) -> AnyStr: pass
def basename(path: AnyStr) -> AnyStr: pass

# NOTE: Empty List[bytes] results in '' (str) => fall back to Any return type.
def commonprefix(list: List[AnyStr]) -> Any: pass
def dirname(path: AnyStr) -> AnyStr: pass
def exists(path: AnyStr) -> bool: pass
def lexists(path: AnyStr) -> bool: pass
def expanduser(path: AnyStr) -> AnyStr: pass
def expandvars(path: AnyStr) -> AnyStr: pass


# These return float if os.stat_float_times() == True
def getatime(path: AnyStr) -> Any: pass
def getmtime(path: AnyStr) -> Any: pass
def getctime(path: AnyStr) -> Any: pass

def getsize(path: AnyStr) -> int: pass
def isabs(path: AnyStr) -> bool: pass
def isfile(path: AnyStr) -> bool: pass
def isdir(path: AnyStr) -> bool: pass
def islink(path: AnyStr) -> bool: pass
def ismount(path: AnyStr) -> bool: pass

def join(path: AnyStr, *paths: AnyStr) -> AnyStr: pass

def normcase(path: AnyStr) -> AnyStr: pass
def normpath(path: AnyStr) -> AnyStr: pass
def realpath(path: AnyStr) -> AnyStr: pass
def relpath(path: AnyStr, start: AnyStr = None) -> AnyStr: pass

def samefile(path1: AnyStr, path2: AnyStr) -> bool: pass
def sameopenfile(fp1: int, fp2: int) -> bool: pass
#def samestat(stat1: stat_result,
#             stat2: stat_result) -> bool: pass  # Unix only

def split(path: AnyStr) -> Tuple[AnyStr, AnyStr]: pass
def splitdrive(path: AnyStr) -> Tuple[AnyStr, AnyStr]: pass
def splitext(path: AnyStr) -> Tuple[AnyStr, AnyStr]: pass

#def splitunc(path: str) -> Tuple[str, str]: pass  # Windows only, deprecated
