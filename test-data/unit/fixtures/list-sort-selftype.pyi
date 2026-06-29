# Builtins stub used in list.sort self-type overload tests.

from typing import TypeVar, Iterable, Iterator, Sequence, overload, Callable

T = TypeVar('T')
SupportsRichComparisonT = TypeVar('SupportsRichComparisonT', bound='SupportsRichComparison')

class object:
    def __init__(self) -> None: pass
    def __eq__(self, other: object) -> bool: pass

class SupportsRichComparison:
    def __lt__(self, other: object) -> bool: pass

class type: pass
class ellipsis: pass

class list(Sequence[T]):
    @overload
    def __init__(self) -> None: pass
    @overload
    def __init__(self, x: Iterable[T]) -> None: pass
    def __iter__(self) -> Iterator[T]: pass
    def __len__(self) -> int: pass
    def __contains__(self, item: object) -> bool: pass
    def __getitem__(self, x: int) -> T: pass
    @overload
    def sort(self: list[SupportsRichComparisonT], *, key: None = None, reverse: bool = False) -> None: ...
    @overload
    def sort(self, *, key: Callable[[T], SupportsRichComparison], reverse: bool = False) -> None: ...

class tuple(Sequence[T]): pass
class function: pass

class int(SupportsRichComparison):
    def __bool__(self) -> bool: pass

class float:
    def __bool__(self) -> bool: pass

class str:
    def __len__(self) -> bool: pass

class bool(int): pass

property = object()

class dict: pass
