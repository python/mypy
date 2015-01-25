from typing import Callable

BOM_UTF8 = b''

class CodecInfo(tuple):
    def __init__(self, *args) -> None: pass

def register(search_function: Callable[[str], CodecInfo]) -> None:
    pass

def lookup(encoding: str) -> CodecInfo:
    pass
