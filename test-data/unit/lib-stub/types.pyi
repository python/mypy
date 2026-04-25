from typing import Any, TypeVar

_T = TypeVar('_T')

def coroutine(func: _T) -> _T: pass

class ModuleType:
    __file__: str
    def __getattr__(self, name: str) -> Any: pass

class GenericAlias:
    def __or__(self, o): ...
    def __ror__(self, o): ...

class NoneType:
    ...

class UnionType:
    def __or__(self, x) -> UnionType: ...

class NotImplementedType: ...
