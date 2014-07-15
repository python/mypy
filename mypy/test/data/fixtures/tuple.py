# Builtins stub used in tuple-related test cases.

from typing import Iterable, typevar

class object:
    def __init__(self): pass

class type: pass

# Current tuple types get special treatment in the type checker, thus there
# is no need for type arguments here.
class tuple: pass

# We need int for indexing tuples.
class int: pass
class str: pass # For convenience

T = typevar('T')

def sum(iterable: Iterable[T], start: T = None) -> T: pass
