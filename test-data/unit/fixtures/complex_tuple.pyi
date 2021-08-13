from typing import Generic, TypeVar, Mapping
_T = TypeVar('_T')
_KT = TypeVar('_KT')
_VT = TypeVar('_VT')

class object:
    def __init__(self): pass

class tuple(Generic[_T]): pass
class dict(Mapping[_KT, _VT]): pass

class type: pass
class function: pass
class int: pass
class float: pass
class complex: pass
class str: pass
class ellipsis: pass
