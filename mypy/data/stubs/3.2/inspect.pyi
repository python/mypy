# Stubs for inspect

from typing import Any, Tuple, List, Callable
from types import FrameType

_object = object

def getmembers(obj: object, predicate: Callable[[Any], bool]) -> List[Tuple[str, object]]: ...

def isclass(obj: object) -> bool: ...

# namedtuple('Attribute', 'name kind defining_class object')
class Attribute(tuple):
    name = ...  # type: str
    kind = ...  # type: str
    defining_class = ...  # type: type
    object = ...  # type: _object

def classify_class_attrs(cls: type) -> List[Attribute]: ...

def cleandoc(doc: str) -> str: ...

def getsourcelines(obj: object) -> Tuple[List[str], int]: ...

# namedtuple('ArgSpec', 'args varargs keywords defaults')
class ArgSpec(tuple):
    args = ...  # type: List[str]
    varargs = ...  # type: str
    keywords = ...  # type: str
    defaults = ...  # type: tuple

def getargspec(func: object) -> ArgSpec: ...

def stack() -> List[Tuple[FrameType, str, int, str, List[str], int]]: ...
