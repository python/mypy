from typing import Generic, TypeVar
T = TypeVar('T')

class object:
    def __init__(self): pass

class type: pass
class tuple(Generic[T]): pass
class function: pass
class int: pass
class str: pass
class unicode: pass
class bool: pass
class ellipsis: pass

class BaseException: pass
class Exception(BaseException): pass
