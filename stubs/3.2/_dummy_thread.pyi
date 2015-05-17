# Stubs for _dummy_thread

# NOTE: These are incomplete!

from typing import Undefined, Any

class LockType:
    def acquire(self) -> None: pass
    def release(self) -> None: pass

def allocate_lock() -> LockType: pass
