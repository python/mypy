# Builtins test fixture with a type alias 'bytes'

class object:
    def __init__(self) -> None: pass
class type:
    def __init__(self, x) -> None: pass

class int: pass
class str: pass
class function: pass

bytes = str
