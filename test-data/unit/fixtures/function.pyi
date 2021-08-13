from typing import TypeVar, Mapping
KT = TypeVar('KT')
VT = TypeVar('VT')

class object:
    def __init__(self): pass

class type: pass
class function: pass
class int: pass
class str: pass
class dict(Mapping[KT, VT]): pass
