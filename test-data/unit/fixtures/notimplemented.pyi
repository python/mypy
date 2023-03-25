# builtins stub used in NotImplemented related cases.
from typing import Any, cast


class object:
    def __init__(self) -> None: pass

class type: pass
class function: pass
class bool: pass
class int: pass
class str: pass
NotImplemented = cast(Any, None)
class dict: pass
