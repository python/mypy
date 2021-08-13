# Builtins stub used in some tuple-related test cases.
#
# This is a simpler version of tuple.py which is useful
# and makes some test cases easier to write/debug.

from typing import Iterable, TypeVar, Generic, Mapping

T = TypeVar('T')
KT = TypeVar('KT')
VT = TypeVar('VT')

class object:
    def __init__(self): pass

class type: pass
class tuple(Generic[T]):
    def __getitem__(self, x: int) -> T: pass
class dict(Mapping[KT, VT]): pass
class function: pass

# We need int for indexing tuples.
class int: pass
class str: pass # For convenience
