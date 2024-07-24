# Builtins stub used in check-narrowing test cases.
from typing import Generic, Sequence, Tuple, Type, TypeVar, Union, Iterable


Tco = TypeVar('Tco', covariant=True)
KT = TypeVar("KT")
VT = TypeVar("VT")

class object:
    def __init__(self) -> None: pass

class type: pass
class tuple(Sequence[Tco], Generic[Tco]): pass
class function: pass
class ellipsis: pass
class int: pass
class str: pass
class float: pass
class dict(Generic[KT, VT]): pass

def isinstance(x: object, t: Union[Type[object], Tuple[Type[object], ...]]) -> bool: pass

class list(Sequence[Tco]):
    def __contains__(self, other: object) -> bool: pass
class set(Iterable[Tco], Generic[Tco]):
    def __init__(self, iterable: Iterable[Tco] = ...) -> None: ...
    def __contains__(self, item: object) -> bool: pass
