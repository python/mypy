# Builtins stub used in list-related test cases.
#
# This is a simpler version of list.pyi

from typing import Sequence, TypeVar

T = TypeVar('T')

class object:
    def __init__(self) -> None: pass

class list(Sequence[T]): pass
class type: pass
class int: pass
class str: pass
class dict: pass
