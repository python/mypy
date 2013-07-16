import typing

class object:
    def __init__(self) -> None: pass

class type:
    def __init__(self, x) -> None: pass

def isinstance(x: object, t: type) -> bool: pass

class int: pass
class bool(int): pass
class str: pass
