# builtins stub used in boolean-related test cases.
from typing import Any, Generic, TypeVar, overload
T = TypeVar('T')

class object:
    def __init__(self) -> None: pass
    def __eq__(self, other: object) -> bool: pass
    def __ne__(self, other: object) -> bool: pass

class type: pass
class tuple(Generic[T]): pass
class function: pass
class int: pass
class bool(int): pass
class float: pass
class str: pass
class unicode: pass
class ellipsis: pass
class list: pass

@overload
def getattr(__o: object, name: str) -> Any: ...
@overload
def getattr(__o: object, name: str, __default: None) -> Any | None: ...
@overload
def getattr(__o: object, name: str, __default: bool) -> Any | bool: ...
@overload
def getattr(__o: object, name: str, __default: T) -> Any | T: ...
