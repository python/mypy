# Stubs for logging.handlers

# NOTE: These are incomplete!

from typing import Any

class BufferingHandler:
    def __init__(self, capacity: int) -> None: pass
    def emit(self, record: Any) -> None: pass
    def flush(self) -> None: pass
    def shouldFlush(self, record: Any) -> bool: pass
