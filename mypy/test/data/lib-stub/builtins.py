class object:
    def __init__(self) -> None: pass

class type:
    def __init__(self, x) -> None: pass

# These are provided here for convenience.
class int: pass
class str: pass

# mypy automatically defines True, False, and __debug__ when builtins are imported.
# They are of type bool, so bool must be defined here.
class bool: pass

class tuple: pass
class function: pass

class ellipsis: pass

# Definition of None is implicit
