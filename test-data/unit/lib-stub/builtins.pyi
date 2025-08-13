# DO NOT ADD TO THIS FILE AS IT WILL SLOW DOWN TESTS!
#
# Use [builtins fixtures/...pyi] if you need more features.

import _typeshed

class object:
    def __init__(self) -> None: pass

class type:
    def __init__(self, x: object) -> None: pass

# These are provided here for convenience.
class int:
    def __add__(self, other: int) -> int: pass
class bool(int): pass
class float: pass

class str: pass
class bytes: pass

class function:
    __name__: str
class ellipsis: pass

from typing import Generic, Iterator, Sequence, TypeVar
_T = TypeVar('_T')
_Tuple_co = TypeVar('_Tuple_co', covariant=True)
class tuple(Generic[_Tuple_co]):
    def __iter__(self) -> Iterator[_Tuple_co]: pass

class list(Generic[_T], Sequence[_T]):
    def __contains__(self, item: object) -> bool: pass
    def __getitem__(self, key: int) -> _T: pass
    def __iter__(self) -> Iterator[_T]: pass

class dict: pass

# Definition of None is implicit
