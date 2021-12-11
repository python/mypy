from typing import Generic, TypeVar
_T = TypeVar('_T')

Any = 0

class object:
    def __init__(self):
        # type: () -> None
        pass

class type:
    def __init__(self, x):
        # type: (Any) -> None
        pass

# These are provided here for convenience.
class int: pass
class float: pass

class str: pass
class unicode: pass

class tuple(Generic[_T]): pass
class function: pass

class ellipsis: pass

def print(*args, end=''): pass

# Definition of None is implicit
