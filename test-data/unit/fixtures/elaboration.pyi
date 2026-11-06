# Builtins stub for function-body elaboration tests.

from typing import Any, Generic, TypeVar

T = TypeVar("T")
K = TypeVar("K")
V = TypeVar("V")

class object:
    def __init__(self) -> None: pass

class type:
    def __init__(self, x: object) -> None: pass

class int: pass
class bool(int): pass
class float: pass
class bytes: pass

class str:
    def __init__(self, object: object = "") -> None: pass


class tuple(Generic[T]): pass
class list(Generic[T]): pass
class dict(Generic[K, V]): pass
class function: pass
