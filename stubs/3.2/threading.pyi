# Stubs for threading

# NOTE: These are incomplete!

from typing import Any, Dict, Optional, Callable, TypeVar, Union

class Thread:
    name = ''
    ident = 0
    daemon = False

    def __init__(self, group: Any = None, target: Any = None, args: Any = (),
                 kwargs: Dict[Any, Any] = None,
                 verbose: Any = None) -> None: pass
    def start(self) -> None: pass
    def run(self) -> None: pass
    def join(self, timeout: float = 0.0) -> None: pass
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
    def wait(self, timeout: float = 0.0) -> bool: pass

class Lock:
    def acquire(self, blocking: bool = True, timeout: float = -1.0) -> bool: pass
    def release(self) -> None: pass
    def __enter__(self) -> bool: pass
    def __exit__(self, *args): pass

class RLock:
    def acquire(self, blocking: bool = True,
                timeout: float = -1.0) -> Optional[bool]: pass
    def release(self) -> None: pass
    def __enter__(self) -> bool: pass
    def __exit__(self, *args): pass

_T = TypeVar('_T')

class Condition:
    def acquire(self, blocking: bool = True, timeout: float = -1.0) -> bool: pass
    def release(self) -> None: pass
    def notify(self, n: int = 1) -> None: pass
    def notify_all(self) -> None: pass
    def wait(self, timeout: float = None) -> bool: pass
    def wait_for(self, predicate: Callable[[], _T], timeout: float = None) -> Union[_T, bool]: pass
    def __enter__(self) -> bool: pass
    def __exit__(self, *args): pass
