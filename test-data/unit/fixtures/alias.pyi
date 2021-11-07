# Builtins test fixture with a type alias 'bytes'
from typing import TypeVar, Mapping
KT = TypeVar('KT')
VT = TypeVar('VT')

from typing import Mapping, Iterable  # needed for `ArgumentInferContext`

class object:
    def __init__(self) -> None: pass
class type:
    def __init__(self, x) -> None: pass

class int: pass
class str: pass
class function: pass
class dict(Mapping[KT, VT]): pass

bytes = str
