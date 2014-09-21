# Builtins stub used in tuple-related test cases.

from typing import Iterable, typevar

class object:
    def __init__(self): pass

class type: pass
class tuple: pass
class function: pass

# We need int for indexing tuples.
class int: pass
class str: pass # For convenience

T = typevar('T')

def sum(iterable: Iterable[T], start: T = None) -> T: pass
