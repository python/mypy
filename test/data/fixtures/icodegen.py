# These builtins stubs are used implicitly in parse-tree to icode generation
# test cases (testicodegen.py and test/data/icode-basic.test).

from typing import typevar, Generic

t = typevar('t')

class object:
    def __init__(self) -> None: pass

class type: pass
class str: pass

# Primitive types are special in generated code.

class int:
    def __add__(self, n: int) -> int: pass
    def __sub__(self, n: int) -> int: pass
    def __mul__(self, n: int) -> int: pass
    def __neg__(self) -> int: pass
    def __eq__(self, n: int) -> bool: pass
    def __ne__(self, n: int) -> bool: pass
    def __lt__(self, n: int) -> bool: pass
    def __gt__(self, n: int) -> bool: pass
    def __le__(self, n: int) -> bool: pass
    def __ge__(self, n: int) -> bool: pass

class float: pass
class bool: pass

class list(Generic[t]): pass

def print(*object) -> None: pass
