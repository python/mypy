# Stubs for threading

# NOTE: These are incomplete!

from typing import Any, Dict

class Thread:
    name = ''
    ident = 0
    daemon = False

    def __init__(self, group: Any = None, target: Any = None, args: Any = (),
                 kwargs: Dict[Any, Any] = None,
                 verbose: Any = None) -> None: pass
    def start(self) -> None: pass
    def run(self) -> None: pass
    # TODO None value for float
    def join(self, timeout: float = None) -> None: pass
    def is_alive(self) -> bool: pass

    # Legacy methods
    def getName(self) -> str: pass
    def setName(self, name: str) -> None: pass
    def isDaemon(self) -> bool: pass
    def setDaemon(self, daemon: bool) -> None: pass

class Event:
    def is_set(self) -> bool: pass
    def set(self) -> None: pass
    def clear(self) -> None: pass
    # TODO can it return None?
    # TOOD None value for float
    def wait(self, timeout: float = None) -> bool: pass

class RLock:
    # TODO may return None
    def acquire(self, blocking: bool = True,
                timeout: float = -1.0) -> bool: pass
    def release(self) -> None: pass
    def __enter__(self) -> bool: pass
    def __exit__(self, type, value, traceback) -> bool: pass
