from typing import Generic, Sequence, TypeVar

_T = TypeVar('_T')


class object:
    def __init__(self): pass

class type: pass
class int:
    def __bool__(self) -> bool: pass
class bool(int): pass
class list(Generic[_T], Sequence[_T]):
    def __len__(self) -> int: pass
class str:
    def __len__(self) -> int: pass
