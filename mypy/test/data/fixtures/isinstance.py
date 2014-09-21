from typing import builtinclass

@builtinclass
class object:
    def __init__(self) -> None: pass

@builtinclass
class type:
    def __init__(self, x) -> None: pass

class tuple: pass
class function: pass

def isinstance(x: object, t: type) -> bool: pass

@builtinclass
class int: pass
@builtinclass
class bool(int): pass
@builtinclass
class str: pass
