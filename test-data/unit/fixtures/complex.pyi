# Builtins stub used for some float/complex test cases.
# Please don't add tuple to this file, it is used to test incomplete fixtures.

from typing import TypeVar, Mapping

_KT = TypeVar('_KT')
_VT = TypeVar('_VT')

class object:
    def __init__(self): pass

class type: pass
class function: pass
class int: pass
class float: pass
class complex: pass
class str: pass
class dict(Mapping[_KT, _VT]): pass
