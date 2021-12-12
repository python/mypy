from typing import Any, Callable

class object:
    def __init__(self) -> None: pass

class type:
    def __init__(self, x) -> None: pass

class function: pass

staticmethod = object() # Dummy definition.

class property(object):
    def __init__(self, fget: Callable[[Any], Any]) -> None:
        pass

class int:
    @staticmethod
    def from_bytes(bytes: bytes, byteorder: str) -> int: pass

class str: pass
class unicode: pass
class bytes: pass
class ellipsis: pass
