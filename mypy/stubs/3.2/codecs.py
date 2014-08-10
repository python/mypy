from typing import Function

BOM_UTF8 = b''

class CodecInfo(tuple):
    def __init__(self, *args) -> None: pass

def register(search_function: Function[[str], CodecInfo]) -> None:
    pass

def lookup(encoding: str) -> CodecInfo:
    pass
