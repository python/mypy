from typing import Generic, Iterable, Mapping, TypeVar

class object:
    def __init__(self) -> None: pass

class type:
    def __init__(self, x) -> None: pass

class function: pass

class int: pass
class float: pass
class str: pass
class unicode: pass
class tuple: pass

T = TypeVar('T')
class list(Iterable[T], Generic[T]): pass

KT = TypeVar('KT')
VT = TypeVar('VT')
class dict(Iterable[KT], Mapping[KT, VT], Generic[KT, VT]): pass

# Definition of None is implicit
