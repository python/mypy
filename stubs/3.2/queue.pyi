# Stubs for queue

# NOTE: These are incomplete!

from typing import Any

class Queue():
    def get(self, block: bool = True, timeout: float = None) -> Any: ...

class Empty(): ...
