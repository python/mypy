import typing

_T = typing.TypeVar('_T')

class object:
    def __init__(self) -> None: pass

class type:
    def __init__(self, x) -> None: pass
    def mro(self) -> typing.Any: pass

class function: pass

# Dummy definitions.
classmethod = object()
staticmethod = object()

class int:
    @classmethod
    def from_bytes(cls, bytes: bytes, byteorder: str) -> int: pass

class str: pass
class bytes: pass
class bool: pass

class tuple(typing.Generic[_T]): pass
