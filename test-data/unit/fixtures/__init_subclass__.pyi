# builtins stub with object.__init_subclass__

from typing import Mapping, Iterable  # needed for ArgumentInferContext

class object:
    def __init_subclass__(cls) -> None: pass

class type: pass

class int: pass
class bool: pass
class str: pass
class function: pass
class dict: pass
