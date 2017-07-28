import typing

T = typing.TypeVar('T')
U = typing.TypeVar('U')
class list(typing.Sequence[T]): pass

class object:
    def __init__(self): pass
class type: pass
class function: pass
class int: pass
class str: pass
class dict(typing.Generic[T, U]): pass
class set(typing.Generic[T]): pass
class tuple(typing.Generic[T]): pass
class BaseException: pass
class StopIteration(BaseException): pass
class StopAsyncIteration(BaseException): pass
def iter(obj: typing.Any) -> typing.Any: pass
def next(obj: typing.Any) -> typing.Any: pass
class ellipsis: ...
