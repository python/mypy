import typing

class object:
    def __init__(self) -> None: pass

class type:
    def __init__(self, x) -> None: pass

class function: pass

classmethod = object() # Dummy definition.

class bool: pass  # needed for automatic True, False, and __debug__ definitions
class int:
    @classmethod
    def from_bytes(cls, bytes: bytes, byteorder: str) -> int: pass

class str: pass
class bytes: pass
