# builtins stub used in boolean-related test cases.
from typing import Generic, TypeVar
T = TypeVar('T')

class object:
    def __init__(self) -> None: pass
    def __eq__(self, other: object) -> bool: pass
    def __ne__(self, other: object) -> bool: pass

class type: pass
class tuple(Generic[T]): pass
class function: pass
class bool: pass
class int: pass
class float: pass
class str: pass
class unicode: pass
class ellipsis: pass
