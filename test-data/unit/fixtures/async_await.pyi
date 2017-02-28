import typing
class object:
    def __init__(self): pass
class type: pass
class function: pass
class int: pass
class str: pass
class dict: pass
class list: pass
class set: pass
class tuple: pass
class BaseException: pass
class StopIteration(BaseException): pass
class StopAsyncIteration(BaseException): pass
def iter(obj: typing.Any) -> typing.Any: pass
def next(obj: typing.Any) -> typing.Any: pass
