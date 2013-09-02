# Builtins stub used in list-related test cases.

from typing import typevar, Generic, builtinclass

T = typevar('T')

@builtinclass
class object:
    def __init__(self): pass

class type: pass

class list(Generic[T]):
    def __mul__(self, x: int) -> list[T]: pass

class tuple: pass

class int: pass
class str: pass
