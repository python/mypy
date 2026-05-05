from typing import Generic, TypeVar
_T = TypeVar('_T')

class object:
    def __init__(self): pass

class tuple(Generic[_T]): pass

class type: pass
class function: pass
class int: pass
class float: pass
class complex: pass
class str: pass
class ellipsis: pass
class dict: pass
