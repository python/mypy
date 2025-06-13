from typing import Any, TypeVar, Coroutine
import sys

_T = TypeVar('_T')
_U = TypeVar('_U')
_V = TypeVar('_V')

def coroutine(func: _T) -> _T: pass

class ModuleType:
    __file__: str
    def __getattr__(self, name: str) -> Any: pass

class GenericAlias:
    def __or__(self, o): ...
    def __ror__(self, o): ...

class CoroutineType(Coroutine[_T, _U, _V]):
    pass

if sys.version_info >= (3, 10):
    class NoneType:
        ...

    class UnionType:
        def __or__(self, x) -> UnionType: ...
