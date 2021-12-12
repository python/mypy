import typing

_T = typing.TypeVar('_T')

class object:
    def __init__(self) -> None: pass

class type:
    def __init__(self, x: typing.Any) -> None: pass

class function: pass

class property(object):
    def __init__(self, fget: typing.Callable[[typing.Any], typing.Any]) -> None:
        pass

class int: pass
class str: pass
class unicode: pass
class bool: pass
class ellipsis: pass

class tuple(typing.Generic[_T]): pass
