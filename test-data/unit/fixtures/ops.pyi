from typing import overload, Any, Generic, Sequence, Tuple, TypeVar

Tco = TypeVar('Tco', covariant=True)

# This is an extension of transform builtins with additional operations.

class object:
    def __init__(self) -> None: pass
    def __eq__(self, o: 'object') -> 'bool': pass
    def __ne__(self, o: 'object') -> 'bool': pass

class type: pass

class slice: pass

class tuple(Sequence[Tco], Generic[Tco]):
    def __getitem__(self, x: int) -> Tco: pass
    def __eq__(self, x: object) -> bool: pass
    def __ne__(self, x: object) -> bool: pass
    def __lt__(self, x: 'tuple') -> bool: pass
    def __le__(self, x: 'tuple') -> bool: pass
    def __gt__(self, x: 'tuple') -> bool: pass
    def __ge__(self, x: 'tuple') -> bool: pass

class function: pass

class bool: pass

class str:
    def __init__(self, x: 'int') -> None: pass
    def __add__(self, x: 'str') -> 'str': pass
    def __eq__(self, x: object) -> bool: pass
    def startswith(self, x: 'str') -> bool: pass

class unicode: pass

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
    def __pow__(self, x: 'int') -> Any: pass
    def __pos__(self) -> 'int': pass
    def __neg__(self) -> 'int': pass
    def __eq__(self, x: object) -> bool: pass
    def __ne__(self, x: object) -> bool: pass
    def __lt__(self, x: 'int') -> bool: pass
    def __le__(self, x: 'int') -> bool: pass
    def __gt__(self, x: 'int') -> bool: pass
    def __ge__(self, x: 'int') -> bool: pass

class float:
    def __add__(self, x: 'float') -> 'float': pass
    def __radd__(self, x: 'float') -> 'float': pass
    def __div__(self, x: 'float') -> 'float': pass
    def __rdiv__(self, x: 'float') -> 'float': pass
    def __truediv__(self, x: 'float') -> 'float': pass
    def __rtruediv__(self, x: 'float') -> 'float': pass

class BaseException: pass

def __print(a1=None, a2=None, a3=None, a4=None): pass

class ellipsis: pass
