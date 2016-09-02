from typing import Any, Dict, Generic, TypeVar

T = TypeVar('T')
S = TypeVar('S')

class object:
    def __init__(self) -> None: pass
class module:
    __name__ = ...  # type: str
    __file__ = ...  # type: str
    __dict__ = ...  # type: Dict[str, Any]
class type: pass
class function: pass
class int: pass
class str: pass
class bool: pass
class tuple: pass
class dict(Generic[T, S]): pass
