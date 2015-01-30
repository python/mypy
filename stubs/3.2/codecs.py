from typing import Any, BinaryIO, Callable

BOM_UTF8 = b''

class Codec(): pass
class StreamWriter(Codec): pass

class CodecInfo(tuple):
    def __init__(self, *args) -> None: pass

def register(search_function: Callable[[str], CodecInfo]) -> None:
    pass

def register_error(name: str, error_handler: Callable[[UnicodeError], Any]) -> None: pass

def lookup(encoding: str) -> CodecInfo:
    pass

# TODO This Callable is actually a StreamWriter constructor
def getwriter(encoding: str) -> Callable[[BinaryIO], StreamWriter]: pass
