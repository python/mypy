# Builtins stub used in sentinel-related test cases.

import types
from typing import Self

class object:
    def __init__(self) -> None: pass
    def __new__(cls) -> Self: ...

class type: pass
class function:
    __name__: str

class int: pass
class bool(int): pass
class str: pass

class sentinel:
    def __init__(self, name: str, /) -> None: ...

class dict: pass
class tuple: pass

def isinstance(x: object, t: type) -> bool: pass
