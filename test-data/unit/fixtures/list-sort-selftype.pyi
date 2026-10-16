# Builtins stub used in self-type bound overload tests.
from typing import Generic, TypeVar, overload, Callable

T = TypeVar('T')
SupportsRichComparisonT = TypeVar('SupportsRichComparisonT', bound='SupportsRichComparison')

class object:
    def __init__(self) -> None: pass

class type: pass
class ellipsis: pass

class SupportsRichComparison:
    def __lt__(self, other: object) -> bool: ...

class int(SupportsRichComparison): pass
class str: pass
class bool(int): pass
class float: pass

class list(Generic[T]):
    @overload
    def sort(self: list[SupportsRichComparisonT], *, key: None = None, reverse: bool = False) -> None: ...
    @overload
    def sort(self, *, key: Callable[[T], SupportsRichComparison], reverse: bool = False) -> None: ...

class dict: pass
class function: pass
