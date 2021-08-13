import typing

_T = typing.TypeVar('_T')
_KT = typing.TypeVar('_KT')
_VT = typing.TypeVar('_VT')

class object:
    def __init__(self) -> None: pass

class type:
    def __init__(self, x: typing.Any) -> None: pass

class function: pass

property = object()  # Dummy definition

class int: pass
class str: pass
class unicode: pass
class bool: pass
class ellipsis: pass

class tuple(typing.Generic[_T]): pass
class dict(typing.Mapping[_KT, _VT]): pass
