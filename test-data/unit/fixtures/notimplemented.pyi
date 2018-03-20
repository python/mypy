# builtins stub used in NotImplemented related cases.
from typing import Any, cast


class object:
    __class__ = None
    def __init__(self) -> None: pass

class type: pass
class function: pass
class bool:
    def __init__(self, o: Any) -> None: pass
class int: pass
class str: pass
NotImplemented = cast(Any, None)
