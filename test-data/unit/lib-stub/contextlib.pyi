from typing import Generic, TypeVar, Callable, Iterator
from typing import ContextManager as ContextManager

_T = TypeVar('_T')

class GeneratorContextManager(ContextManager[_T], Generic[_T]):
    def __call__(self, func: Callable[..., _T]) -> Callable[..., _T]: ...

def contextmanager(func: Callable[..., Iterator[_T]]) -> Callable[..., GeneratorContextManager[_T]]:
    ...
