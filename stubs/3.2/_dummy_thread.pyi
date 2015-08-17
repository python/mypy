# Stubs for _dummy_thread

# NOTE: These are incomplete!

from typing import Any

class LockType:
    def acquire(self) -> None: ...
    def release(self) -> None: ...

def allocate_lock() -> LockType: ...
