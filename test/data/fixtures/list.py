# Builtins stub used in list-related test cases.

from typing import typevar, Generic

T = typevar('T')

class object:
    def __init__(self): pass

class type: pass

class list(Generic[T]): pass

class tuple: pass

class int: pass
class str: pass
