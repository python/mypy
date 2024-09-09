from typing import Any, TypeVar
import sys

_T = TypeVar('_T')

def coroutine(func: _T) -> _T: pass

class ModuleType:
    __file__: str
    def __getattr__(self, name: str) -> Any: pass

class GenericAlias:
    def __or__(self, o): ...
    def __ror__(self, o): ...

if sys.version_info >= (3, 10):
    class NoneType:
        ...

    class UnionType:
        def __or__(self, x) -> UnionType: ...
