# Stubs for struct

# Based on http://docs.python.org/3.2/library/struct.html

from typing import overload, Any, Undefined

class error(Exception): pass

@overload
def pack(fmt: str, *v: Any) -> bytes: pass
@overload
def pack(fmt: bytes, *v: Any) -> bytes: pass

@overload
def pack_into(fmt: str, buffer: Any, offset: int, *v: Any) -> None: pass
# TODO buffer type
@overload
def pack_into(fmt: bytes, buffer: Any, offset: int, *v: Any) -> None: pass

# TODO return type should be tuple
# TODO buffer type
@overload
def unpack(fmt: str, buffer: Any) -> Any: pass
@overload
def unpack(fmt: bytes, buffer: Any) -> Any: pass

@overload
def unpack_from(fmt: str, buffer: Any) -> Any: pass
@overload
def unpack_from(fmt: bytes, buffer: Any, offset: int = 0) -> Any: pass

@overload
def calcsize(fmt: str) -> int: pass
@overload
def calcsize(fmt: bytes) -> int: pass

class Struct:
    format = b''
    size = 0

    @overload
    def __init__(self, format: str) -> None: pass
    @overload
    def __init__(self, format: bytes) -> None: pass

    def pack(self, *v: Any) -> bytes: pass
    # TODO buffer type
    def pack_into(self, buffer: Any, offset: int, *v: Any) -> None: pass
    # TOTO return type should be tuple
    # TODO buffer type
    def unpack(self, buffer: Any) -> Any: pass
    def unpack_from(self, buffer: Any, offset: int = 0) -> Any: pass
