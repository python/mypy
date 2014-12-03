# Stubs for fcntl

# NOTE: These are incomplete!

import typing

FD_CLOEXEC = 0
F_GETFD = 0
F_SETFD = 0

def fcntl(fd: int, op: int, arg: int = 0) -> int: pass
