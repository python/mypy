# builtins stub used in type-related test cases.

from typing import builtinclass, Generic, TypeVar, List

T = TypeVar('T')

@builtinclass
class object:
    def __init__(self) -> None: pass
    def __str__(self) -> 'str': pass

class list(Generic[T]): pass

class type:
    def mro(self) -> List['type']: pass

class tuple: pass
class function: pass
class bool: pass
class int: pass
class str: pass
class unicode: pass