# Builtins stub used in dictionary-related test cases.

from typing import typevar, Generic

T = typevar('T')
S = typevar('S')

class object:
    def __init__(self) -> None: pass

class type: pass

class dict(Generic[T, S]): pass
class int: pass # for convenience
class str: pass # for keyword argument key type
class list(Generic[T]): pass # needed by some test cases
