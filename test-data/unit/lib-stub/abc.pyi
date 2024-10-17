from typing import Type, Any, TypeVar

T = TypeVar('T', bound=Type[Any])

class ABCMeta(type):
    def register(cls, tp: T) -> T: pass
class ABC(metaclass=ABCMeta): pass
abstractmethod = object()
abstractproperty = object()
