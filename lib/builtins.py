# Builtins for the native back end

# TODO this still in early stages of development

from typing import typevar, Generic

T = typevar('T')

class object:
    def __init__(self) -> None: pass

class type: pass
class str: pass

# Primitive types are special in generated code.

class int:
    def __add__(self, n: int) -> int: pass
    def __sub__(self, n: int) -> int: pass
    def __mul__(self, n: int) -> int: pass
    def __floordiv__(self, n: int) -> int: pass
    def __mod__(self, n: int) -> int: pass
    def __neg__(self) -> int: pass
    def __and__(self, n: int) -> int: pass
    def __or__(self, n: int) -> int: pass
    def __xor__(self, n: int) -> int: pass
    def __lshift__(self, n: int) -> int: pass
    def __rshift__(self, n: int) -> int: pass
    def __invert__(self) -> int: pass
    def __eq__(self, n: int) -> bool: pass
    def __ne__(self, n: int) -> bool: pass
    def __lt__(self, n: int) -> bool: pass
    def __gt__(self, n: int) -> bool: pass
    def __le__(self, n: int) -> bool: pass
    def __ge__(self, n: int) -> bool: pass

class float: pass
class bool: pass

class list(Generic[T]): pass

def print(*object) -> None: pass
