# Stubs for os.path
# Ron Murawski <ron@horizonchess.com>

# based on http://docs.python.org/3.2/library/os.path.html

from typing import Any, List, Tuple, IO, overload

# ----- os.path variables -----
supports_unicode_filenames = False

# ----- os.path function stubs -----
def abspath(path: str) -> str: pass
def basename(path) -> str: pass
def commonprefix(list: List[str]) -> str: pass
def dirname(path: str) -> str: pass
def exists(path: str) -> bool: pass
def lexists(path: str) -> bool: pass
def expanduser(path: str) -> str: pass
def expandvars(path: str) -> str: pass
def getatime(path: str) -> int:
    pass # return float if os.stat_float_times() returns True
def getmtime(path: str) -> int:
    pass # return float if os.stat_float_times() returns True
def getctime(path: str) -> int:
    pass # return float if os.stat_float_times() returns True
def getsize(path: str) -> int: pass
def isabs(path: str) -> bool: pass
def isfile(path: str) -> bool: pass
def isdir(path: str) -> bool: pass
def islink(path: str) -> bool: pass
def ismount(path: str) -> bool: pass
def join(path: str, *paths: str) -> str: pass
def normcase(path: str) -> str: pass
def normpath(path: str) -> str: pass
def realpath(path: str) -> str: pass
def relpath(path: str, start: str = None) -> str: pass
def samefile(path1: str, path2: str) -> bool: pass

def sameopenfile(fp1: IO[Any], fp2: IO[Any]) -> bool: pass

#def samestat(stat1: stat_result, stat2: stat_result) -> bool:
#    pass  # Unix only
def split(path: str) -> Tuple[str, str]: pass
def splitdrive(path: str) -> Tuple[str, str]: pass
def splitext(path: str) -> Tuple[str, str]: pass
#def splitunc(path: str) -> Tuple[str, str] : pass  # Windows only, deprecated
