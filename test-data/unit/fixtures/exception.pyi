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

# Note: this is a slight simplification. In Python 2, the inheritance hierarchy
# is actually Exception -> StandardError -> RuntimeError -> ...
class BaseException:
    def __init__(self, *args: object) -> None: ...
class Exception(BaseException): pass
class RuntimeError(Exception): pass
class NotImplementedError(RuntimeError): pass

