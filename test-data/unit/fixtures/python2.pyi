from typing import Generic, Iterable, TypeVar

class object:
    def __init__(self) -> None: pass

class type:
    def __init__(self, x) -> None: pass

class function: pass

class int: pass
class str: pass
class unicode: pass
class bool: pass

T = TypeVar('T')
class list(Iterable[T], Generic[T]): pass

# Definition of None is implicit
