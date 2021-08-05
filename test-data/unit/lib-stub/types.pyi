from typing import TypeVar
import sys

_T = TypeVar('_T')

def coroutine(func: _T) -> _T: pass

class bool: ...

class ModuleType:
    __file__ = ... # type: str

if sys.version_info >= (3, 10):
    class Union:
        def __or__(self, x) -> Union: ...
