from typing import Union
import io

FASYNC = 64

FD_CLOEXEC = 1

F_DUPFD = 0
F_FULLFSYNC = 51
F_GETFD = 1
F_GETFL = 3
F_GETLK = 7
F_GETOWN = 5
F_RDLCK = 1
F_SETFD = 2
F_SETFL = 4
F_SETLK = 8
F_SETLKW = 9
F_SETOWN = 6
F_UNLCK = 2
F_WRLCK = 3

LOCK_EX = 2
LOCK_NB = 4
LOCK_SH = 1
LOCK_UN = 8

_ANYFILE = Union[int, io.IOBase]

def fcntl(fd: _ANYFILE, op: int, arg: Union[int, str] = 0) -> Union[int, str]: ...

# TODO: arg: int or read-only buffer interface or read-write buffer interface
def ioctl(fd: _ANYFILE, op: int, arg: Union[int, str] = 0,
          mutate_flag: bool = True) -> Union[int, str]: ...

def flock(fd: _ANYFILE, op: int) -> None: ...
def lockf(fd: _ANYFILE, op: int, length: int = 0, start: int = 0,
          whence: int = 0) -> Union[int, str]: ...
