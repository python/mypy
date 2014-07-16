# Stubs for inspect

from typing import Undefined, Any, Tuple, List, Function

_object = object

def getmembers(obj: object, predicate: Function[[Any], bool]) -> List[Tuple[str, object]]: pass

def isclass(obj: object) -> bool: pass

# namedtuple('Attribute', 'name kind defining_class object')
class Attribute(tuple):
    name = Undefined(str)
    kind = Undefined(str)
    defining_class = Undefined(type)
    object = Undefined(_object)

def classify_class_attrs(cls: type) -> List[Attribute]: pass

def cleandoc(doc: str) -> str: pass

def getsourcelines(obj: object) -> Tuple[List[str], int]: pass

# namedtuple('ArgSpec', 'args varargs keywords defaults')
class ArgSpec(tuple):
    args = Undefined(List[str])
    varargs = Undefined(str)
    keywords = Undefined(str)
    defaults = Undefined(tuple)

def getargspec(func: object) -> ArgSpec: pass
