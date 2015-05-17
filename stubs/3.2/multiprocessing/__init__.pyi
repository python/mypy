# Stubs for multiprocessing

from typing import Any

class Lock(): pass
class Process(): pass

class Queue():
    def get(block: bool = None, timeout: float = None) -> Any: pass

class Value():
    def __init__(typecode_or_type: str, *args: Any, lock: bool = True) -> None: pass
