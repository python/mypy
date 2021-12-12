from typing import Type, Any, TypeVar

T = TypeVar('T', bound=Type[Any])

class ABC(type): pass
class ABCMeta(type):
    def register(cls, tp: T) -> T: pass

abstractmethod = object()

class abstractproperty(property):
    def __init__(self, fget: Callable[[Any], Any]) -> None:
        pass
