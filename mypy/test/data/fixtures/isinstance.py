from typing import builtinclass

class object:
    def __init__(self) -> None: pass

class type:
    def __init__(self, x) -> None: pass

class tuple: pass
class function: pass

def isinstance(x: object, t: type) -> bool: pass

class int: pass
class float: pass
class bool(int): pass
class str: pass
