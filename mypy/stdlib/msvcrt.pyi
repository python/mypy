# Stubs for msvcrt

# NOTE: These are incomplete!

LK_LOCK: int
LK_NBLCK: int
LK_NBRLCK: int
LK_RLCK: int
LK_UNLCK: int

def locking(__fd: int, __mode: int, __nbytes: int) -> None: ...

def get_osfhandle(__fd: int) -> int: ...
def open_osfhandle(__handle: int, __flags: int) -> int: ...
