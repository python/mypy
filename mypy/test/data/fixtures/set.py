# Builtins stub used in set-related test cases.

from typing import typevar, Generic

T = typevar('T')

class object:
    def __init__(self) -> None: pass

class type: pass

class int: pass
class str: pass
class tuple: pass

class set(Generic[T]): pass
