from typing import Any, TypeVar
import sys

_T = TypeVar('_T')

def coroutine(func: _T) -> _T: pass

class ModuleType:
    __file__: str
    def __getattr__(self, name: str) -> Any: pass

if sys.version_info >= (3, 10):
    class Union:
        def __or__(self, x) -> Union: ...

    class NoneType:
        ...
