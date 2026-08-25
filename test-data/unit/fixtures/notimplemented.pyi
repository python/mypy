# builtins stub used in NotImplemented related cases.

class object:
    def __init__(self) -> None: pass

class type: pass
class function: pass
class bool: pass
class int: pass
class str: pass
class dict: pass
class tuple: pass
class ellipsis: pass
class list: pass

from types import NotImplementedType
NotImplemented: NotImplementedType

class BaseException: pass
