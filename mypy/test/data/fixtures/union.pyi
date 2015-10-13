# Builtins stub used in tuple-related test cases.

from isinstance import isinstance
from typing import Iterable, TypeVar

class object:
    def __init__(self): pass

class type: pass
class function: pass

# Current tuple types get special treatment in the type checker, thus there
# is no need for type arguments here.
class tuple: pass

# We need int for indexing tuples.
class int: pass
class str: pass # For convenience
