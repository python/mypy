from typing import overload, Any, Generic, Sequence, Tuple, TypeVar, Optional

Tco = TypeVar('Tco', covariant=True)

# This is an extension of transform builtins with additional operations.

class object:
    def __init__(self) -> None: pass
    def __eq__(self, o: 'object') -> 'bool': pass
    def __ne__(self, o: 'object') -> 'bool': pass

class type: pass

class slice: pass

class tuple(Sequence[Tco]):
    def __getitem__(self, x: int) -> Tco: pass
    def __eq__(self, x: object) -> bool: pass
    def __ne__(self, x: object) -> bool: pass
    def __lt__(self, x: Tuple[Tco, ...]) -> bool: pass
    def __le__(self, x: Tuple[Tco, ...]) -> bool: pass
    def __gt__(self, x: Tuple[Tco, ...]) -> bool: pass
    def __ge__(self, x: Tuple[Tco, ...]) -> bool: pass

class function: pass

class str:
    def __init__(self, x: 'int') -> None: pass
    def __add__(self, x: 'str') -> 'str': pass
    def __eq__(self, x: object) -> bool: pass
    def startswith(self, x: 'str') -> bool: pass
    def strip(self) -> 'str': pass

class int:
    def __add__(self, x: 'int') -> 'int': pass
    def __radd__(self, x: 'int') -> 'int': pass
    def __sub__(self, x: 'int') -> 'int': pass
    def __mul__(self, x: 'int') -> 'int': pass
    def __div__(self, x: 'int') -> 'int': pass
    def __rdiv__(self, x: 'int') -> 'int': pass
    def __truediv__(self, x: 'int') -> 'int': pass
    def __rtruediv__(self, x: 'int') -> 'int': pass
    def __mod__(self, x: 'int') -> 'int': pass
    def __floordiv__(self, x: 'int') -> 'int': pass
    def __pow__(self, x: 'int', __modulo: Optional[int] = ...) -> Any: pass
    def __pos__(self) -> 'int': pass
    def __neg__(self) -> 'int': pass
    def __eq__(self, x: object) -> bool: pass
    def __ne__(self, x: object) -> bool: pass
    def __lt__(self, x: 'int') -> bool: pass
    def __le__(self, x: 'int') -> bool: pass
    def __gt__(self, x: 'int') -> bool: pass
    def __ge__(self, x: 'int') -> bool: pass

class bool(int): pass

class float:
    def __add__(self, x: 'float') -> 'float': pass
    def __radd__(self, x: 'float') -> 'float': pass
    def __div__(self, x: 'float') -> 'float': pass
    def __rdiv__(self, x: 'float') -> 'float': pass
    def __truediv__(self, x: 'float') -> 'float': pass
    def __rtruediv__(self, x: 'float') -> 'float': pass

class complex:
    def __add__(self, x: complex) -> complex: pass
    def __radd__(self, x: complex) -> complex: pass

class BaseException: pass

def __print(a1: object = None, a2: object = None, a3: object = None,
            a4: object = None) -> None: pass

class ellipsis: pass

class dict: pass
