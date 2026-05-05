# Builtins test fixture with a type alias 'bytes'

from typing import Mapping, Iterable  # needed for `ArgumentInferContext`

class object:
    def __init__(self) -> None: pass
class type:
    def __init__(self, x) -> None: pass

class int: pass
class str: pass
class function: pass

bytes = str

class dict: pass
