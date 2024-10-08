# builtins stub used in NotImplemented related cases.
from typing import Any

class object:
    def __init__(self) -> None: pass

class type: pass
class function: pass
class bool: pass
class int: pass
class str: pass
class dict: pass

class _NotImplementedType(Any):
    __call__: NotImplemented  # type: ignore
NotImplemented: _NotImplementedType

class BaseException: pass
