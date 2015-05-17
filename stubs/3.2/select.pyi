# Stubs for select

# NOTE: These are incomplete!

from typing import Any, Tuple, List, Sequence

class error(Exception): pass

POLLIN = 0
POLLPRI = 0
POLLOUT = 0
POLLERR = 0
POLLHUP = 0
POLLNVAL = 0

class poll:
    def __init__(self) -> None: pass
    def register(self, fd: Any,
                 eventmask: int = POLLIN|POLLPRI|POLLOUT) -> None: pass
    def modify(self, fd: Any, eventmask: int) -> None: pass
    def unregister(self, fd: Any) -> None: pass
    def poll(self, timeout: int = None) -> List[Tuple[int, int]]: pass

def select(rlist: Sequence, wlist: Sequence, xlist: Sequence,
           timeout: float = None) -> Tuple[List[int],
                                           List[int],
                                           List[int]]: pass
