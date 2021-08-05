from typing import Type, Any, TypeVar

T = TypeVar('T', bound=Type[Any])

class ABC(type): pass
class ABCMeta(type):
    def register(cls, tp: T) -> T: pass
abstractmethod = object()
abstractproperty = object()
