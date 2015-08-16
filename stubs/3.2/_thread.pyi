# Stubs for _thread

# NOTE: These are incomplete!

from typing import Any

def _count() -> int: ...
_dangling = ...  # type: Any

class LockType:
    def acquire(self) -> None: ...
    def release(self) -> None: ...

def allocate_lock() -> LockType: ...
