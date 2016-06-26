class Any: pass

class object:
    def __init__(self) -> None: pass

class type:
    def __init__(self, x: Any) -> None: pass

# These are provided here for convenience.
class int:
    def __add__(self, other: 'int') -> 'int': pass
class str:
    def __add__(self, other: 'str') -> 'str': pass

class tuple: pass
class function: pass

class ellipsis: pass

# Definition of None is implicit
