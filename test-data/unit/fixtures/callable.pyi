from typing import Generic, Tuple, TypeVar, Union

T = TypeVar('T')

class object:
    def __init__(self) -> None: pass

class type:
    def __init__(self, x) -> None: pass

class tuple(Generic[T]): pass

class function: pass

def isinstance(x: object, t: Union[type, Tuple[type, ...]]) -> bool: pass

def callable(x: object) -> bool: pass

class int:
    def __add__(self, other: 'int') -> 'int': pass
    def __eq__(self, other: 'int') -> 'bool': pass
class float: pass
class bool(int): pass
class str:
    def __add__(self, other: 'str') -> 'str': pass
    def __eq__(self, other: 'str') -> bool: pass
class ellipsis: pass
