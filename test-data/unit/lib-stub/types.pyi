from typing import TypeVar, Optional, List, Any, Generic, Sequence
T = TypeVar('T')

def coroutine(func: T) -> T:
    return func

class bool: ...

class ModuleType: ...
