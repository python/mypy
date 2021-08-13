# builtins stub used in NotImplemented related cases.
from typing import Any, cast, TypeVar, Mapping
KT = TypeVar('KT')
VT = TypeVar('VT')

class object:
    def __init__(self) -> None: pass

class type: pass
class function: pass
class bool: pass
class int: pass
class str: pass
class dict(Mapping[KT, VT]): pass
NotImplemented = cast(Any, None)
