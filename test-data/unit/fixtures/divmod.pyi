from typing import TypeVar, Tuple, SupportsInt, Mapping
KT = TypeVar('KT')
VT = TypeVar('VT')

class object:
    def __init__(self): pass

class int(SupportsInt):
    def __divmod__(self, other: int) -> Tuple[int, int]: pass
    def __rdivmod__(self, other: int) -> Tuple[int, int]: pass

class float(SupportsInt):
    def __divmod__(self, other: float) -> Tuple[float, float]: pass
    def __rdivmod__(self, other: float) -> Tuple[float, float]: pass


class tuple: pass
class function: pass
class str: pass
class type: pass
class ellipsis: pass
class dict(Mapping[KT, VT]): pass

_N = TypeVar('_N', int, float)
def divmod(_x: _N, _y: _N) -> Tuple[_N, _N]: ...
