import sys
from typing import IO

_FD = int | IO[str]

if sys.platform != "win32":
    # XXX: Undocumented integer constants
    IFLAG: int
    OFLAG: int
    CFLAG: int
    LFLAG: int
    ISPEED: int
    OSPEED: int
    CC: int
    def setraw(fd: _FD, when: int = ...) -> None: ...
    def setcbreak(fd: _FD, when: int = ...) -> None: ...
