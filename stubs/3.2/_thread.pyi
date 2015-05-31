# Stubs for _thread

# NOTE: These are incomplete!

from typing import Any

def _count() -> int: pass
_dangling = ...  # type: Any

class LockType:
    def acquire(self) -> None: pass
    def release(self) -> None: pass

def allocate_lock() -> LockType: pass
