import sys
from typing import Generic, TypeVar
T = TypeVar('T')

class object:
    def __init__(self): pass

class type: pass
class tuple(Generic[T]):
    def __ge__(self, other: object) -> bool: ...
class list: pass
class dict: pass
class function: pass
class int: pass
class str: pass
class bool: pass
class ellipsis: pass

class BaseException:
    def __init__(self, *args: object) -> None: ...
class Exception(BaseException): pass
class RuntimeError(Exception): pass
class NotImplementedError(RuntimeError): pass

if sys.version_info >= (3, 11):
    _BT_co = TypeVar("_BT_co", bound=BaseException, covariant=True)
    _T_co = TypeVar("_T_co", bound=Exception, covariant=True)
    class BaseExceptionGroup(BaseException, Generic[_BT_co]): ...
    class ExceptionGroup(BaseExceptionGroup[_T_co], Exception): ...
