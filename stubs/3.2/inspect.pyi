# Stubs for inspect

from typing import Any, Tuple, List, Callable

_object = object

def getmembers(obj: object, predicate: Callable[[Any], bool]) -> List[Tuple[str, object]]: pass

def isclass(obj: object) -> bool: pass

# namedtuple('Attribute', 'name kind defining_class object')
class Attribute(tuple):
    name = ...  # type: str
    kind = ...  # type: str
    defining_class = ...  # type: type
    object = ...  # type: _object

def classify_class_attrs(cls: type) -> List[Attribute]: pass

def cleandoc(doc: str) -> str: pass

def getsourcelines(obj: object) -> Tuple[List[str], int]: pass

# namedtuple('ArgSpec', 'args varargs keywords defaults')
class ArgSpec(tuple):
    args = ...  # type: List[str]
    varargs = ...  # type: str
    keywords = ...  # type: str
    defaults = ...  # type: tuple

def getargspec(func: object) -> ArgSpec: pass
