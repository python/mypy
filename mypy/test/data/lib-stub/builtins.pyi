from typing import builtinclass

@builtinclass
class object:
    def __init__(self) -> None: pass

@builtinclass
class type:
    def __init__(self, x) -> None: pass

# These are provided here for convenience.
@builtinclass
class int: pass
@builtinclass
class str: pass

class tuple: pass
class function: pass

@builtinclass
class ellipsis:
    def __init__(self) -> None: pass

# Definition of None is implicit
