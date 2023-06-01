from typing import AsyncIterator, Generic, TypeVar, Callable, Iterator
from typing import ContextManager as ContextManager, AsyncContextManager as AsyncContextManager

_T = TypeVar('_T')

class GeneratorContextManager(ContextManager[_T], Generic[_T]):
    def __call__(self, func: Callable[..., _T]) -> Callable[..., _T]: ...

# This does not match `typeshed` definition, needs `ParamSpec`:
def contextmanager(func: Callable[..., Iterator[_T]]) -> Callable[..., GeneratorContextManager[_T]]:
    ...

def asynccontextmanager(func: Callable[..., AsyncIterator[_T]]) -> Callable[..., AsyncContextManager[_T]]: ...
