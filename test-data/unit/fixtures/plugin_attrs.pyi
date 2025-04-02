# Builtins stub used to support attrs plugin tests.
from typing import Union, overload, Generic, Sequence, TypeVar, Type, Iterable, Iterator

class object:
    def __init__(self) -> None: pass
    def __eq__(self, o: object) -> bool: pass
    def __ne__(self, o: object) -> bool: pass
    def __hash__(self) -> int: ...

class type: pass
class bytes: pass
class function: pass
class float: pass
class int:
    @overload
    def __init__(self, x: Union[str, bytes, int] = ...) -> None: ...
    @overload
    def __init__(self, x: Union[str, bytes], base: int) -> None: ...
class bool(int): pass
class complex:
    @overload
    def __init__(self, real: float = ..., im: float = ...) -> None: ...
    @overload
    def __init__(self, real: str = ...) -> None: ...

class str: pass
class ellipsis: pass
class list: pass
class dict: pass

T = TypeVar("T")
Tco = TypeVar('Tco', covariant=True)
class tuple(Sequence[Tco], Generic[Tco]):
    def __new__(cls: Type[T], iterable: Iterable[Tco] = ...) -> T: ...
    def __iter__(self) -> Iterator[Tco]: pass
    def __contains__(self, item: object) -> bool: pass
    def __getitem__(self, x: int) -> Tco: pass

property = object()  # Dummy definition
