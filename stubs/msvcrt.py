# Stubs for msvcrt

# NOTE: These are incomplete!

from typing import overload, IO, TextIO

@overload
def get_osfhandle(file: IO) -> int: pass
@overload
def get_osfhandle(file: TextIO) -> int: pass

def open_osfhandle(handle: int, flags: int) -> int: pass
