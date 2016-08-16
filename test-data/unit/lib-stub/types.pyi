from typing import TypeVar
T = TypeVar('T')
def coroutine(func: T) -> T:
    return func
