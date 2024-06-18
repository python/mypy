from typing import Tuple, TypeVar, Generic, Union, cast, Any, Type

T = TypeVar('T')

class object:
    def __init__(self) -> None: pass

class type:
    def __init__(self, x) -> None: pass
    def __or__(self, other: type) -> type: pass

class tuple(Generic[T]): pass

class function: pass

def isinstance(x: object, t: Union[Type[object], Tuple[Type[object], ...]]) -> bool: pass
def issubclass(x: object, t: Union[Type[object], Tuple[Type[object], ...]]) -> bool: pass
def hasattr(x: object, name: str) -> bool: pass

class int:
    def __add__(self, other: 'int') -> 'int': pass
class float: pass
class bool(int): pass
class str:
    def __add__(self, other: 'str') -> 'str': pass
class ellipsis: pass

NotImplemented = cast(Any, None)

class dict: pass
