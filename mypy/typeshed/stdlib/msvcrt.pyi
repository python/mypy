import sys
from typing_extensions import Literal

# This module is only available on Windows
if sys.platform == "win32":
    LK_UNLCK: Literal[0]
    LK_LOCK: Literal[1]
    LK_NBLCK: Literal[2]
    LK_RLCK: Literal[3]
    LK_NBRLCK: Literal[4]
    SEM_FAILCRITICALERRORS: int
    SEM_NOALIGNMENTFAULTEXCEPT: int
    SEM_NOGPFAULTERRORBOX: int
    SEM_NOOPENFILEERRORBOX: int
    def locking(__fd: int, __mode: int, __nbytes: int) -> None: ...
    def setmode(__fd: int, __mode: int) -> int: ...
    def open_osfhandle(__handle: int, __flags: int) -> int: ...
    def get_osfhandle(__fd: int) -> int: ...
    def kbhit() -> bool: ...
    def getch() -> bytes: ...
    def getwch() -> str: ...
    def getche() -> bytes: ...
    def getwche() -> str: ...
    def putch(__char: bytes) -> None: ...
    def putwch(__unicode_char: str) -> None: ...
    def ungetch(__char: bytes) -> None: ...
    def ungetwch(__unicode_char: str) -> None: ...
    def heapmin() -> None: ...
