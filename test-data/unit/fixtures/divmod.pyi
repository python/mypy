from typing import TypeVar, Tuple, SupportsInt
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

_N = TypeVar('_N', int, float)
def divmod(_x: _N, _y: _N) -> Tuple[_N, _N]: ...
