# Stubs for struct

# Based on http://docs.python.org/3.2/library/struct.html

from typing import overload, Any, AnyStr

class error(Exception): pass

def pack(fmt: AnyStr, *v: Any) -> bytes: pass
# TODO buffer type
def pack_into(fmt: AnyStr, buffer: Any, offset: int, *v: Any) -> None: pass

# TODO return type should be tuple
# TODO buffer type
def unpack(fmt: AnyStr, buffer: Any) -> Any: pass
def unpack_from(fmt: AnyStr, buffer: Any, offset: int = 0) -> Any: pass

def calcsize(fmt: AnyStr) -> int: pass

class Struct:
    format = b''
    size = 0

    def __init__(self, format: AnyStr) -> None: pass

    def pack(self, *v: Any) -> bytes: pass
    # TODO buffer type
    def pack_into(self, buffer: Any, offset: int, *v: Any) -> None: pass
    # TOTO return type should be tuple
    # TODO buffer type
    def unpack(self, buffer: Any) -> Any: pass
    def unpack_from(self, buffer: Any, offset: int = 0) -> Any: pass
