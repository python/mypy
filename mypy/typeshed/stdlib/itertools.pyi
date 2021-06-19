import sys
from _typeshed import _T_co
from typing import (
    Any,
    Callable,
    Generic,
    Iterable,
    Iterator,
    Optional,
    SupportsComplex,
    SupportsFloat,
    SupportsInt,
    Tuple,
    Type,
    TypeVar,
    Union,
    overload,
)
from typing_extensions import Literal, SupportsIndex

_T = TypeVar("_T")
_S = TypeVar("_S")
_N = TypeVar("_N", int, float, SupportsFloat, SupportsInt, SupportsIndex, SupportsComplex)
_Step = Union[int, float, SupportsFloat, SupportsInt, SupportsIndex, SupportsComplex]

Predicate = Callable[[_T], object]

# Technically count can take anything that implements a number protocol and has an add method
# but we can't enforce the add method
class count(Iterator[_N], Generic[_N]):
    @overload
    def __new__(cls) -> count[int]: ...
    @overload
    def __new__(cls, start: _N, step: _Step = ...) -> count[_N]: ...
    @overload
    def __new__(cls, *, step: _N) -> count[_N]: ...
    def __next__(self) -> _N: ...
    def __iter__(self) -> Iterator[_N]: ...

class cycle(Iterator[_T], Generic[_T]):
    def __init__(self, __iterable: Iterable[_T]) -> None: ...
    def __next__(self) -> _T: ...
    def __iter__(self) -> Iterator[_T]: ...

class repeat(Iterator[_T], Generic[_T]):
    @overload
    def __init__(self, object: _T) -> None: ...
    @overload
    def __init__(self, object: _T, times: int) -> None: ...
    def __next__(self) -> _T: ...
    def __iter__(self) -> Iterator[_T]: ...

class accumulate(Iterator[_T], Generic[_T]):
    if sys.version_info >= (3, 8):
        @overload
        def __init__(self, iterable: Iterable[_T], func: None = ..., *, initial: Optional[_T] = ...) -> None: ...
        @overload
        def __init__(self, iterable: Iterable[_S], func: Callable[[_T, _S], _T], *, initial: Optional[_T] = ...) -> None: ...
    else:
        def __init__(self, iterable: Iterable[_T], func: Optional[Callable[[_T, _T], _T]] = ...) -> None: ...
    def __iter__(self) -> Iterator[_T]: ...
    def __next__(self) -> _T: ...

class chain(Iterator[_T], Generic[_T]):
    def __init__(self, *iterables: Iterable[_T]) -> None: ...
    def __next__(self) -> _T: ...
    def __iter__(self) -> Iterator[_T]: ...
    @classmethod
    # We use Type and not Type[_S] to not lose the type inference from __iterable
    def from_iterable(cls: Type[Any], __iterable: Iterable[Iterable[_S]]) -> Iterator[_S]: ...

class compress(Iterator[_T], Generic[_T]):
    def __init__(self, data: Iterable[_T], selectors: Iterable[Any]) -> None: ...
    def __iter__(self) -> Iterator[_T]: ...
    def __next__(self) -> _T: ...

class dropwhile(Iterator[_T], Generic[_T]):
    def __init__(self, __predicate: Predicate[_T], __iterable: Iterable[_T]) -> None: ...
    def __iter__(self) -> Iterator[_T]: ...
    def __next__(self) -> _T: ...

class filterfalse(Iterator[_T], Generic[_T]):
    def __init__(self, __predicate: Optional[Predicate[_T]], __iterable: Iterable[_T]) -> None: ...
    def __iter__(self) -> Iterator[_T]: ...
    def __next__(self) -> _T: ...

_T1 = TypeVar("_T1")
_T2 = TypeVar("_T2")

class groupby(Iterator[Tuple[_T, Iterator[_S]]], Generic[_T, _S]):
    @overload
    def __new__(cls, iterable: Iterable[_T1], key: None = ...) -> groupby[_T1, _T1]: ...
    @overload
    def __new__(cls, iterable: Iterable[_T1], key: Callable[[_T1], _T2]) -> groupby[_T2, _T1]: ...
    def __iter__(self) -> Iterator[Tuple[_T, Iterator[_S]]]: ...
    def __next__(self) -> Tuple[_T, Iterator[_S]]: ...

class islice(Iterator[_T], Generic[_T]):
    @overload
    def __init__(self, __iterable: Iterable[_T], __stop: Optional[int]) -> None: ...
    @overload
    def __init__(
        self, __iterable: Iterable[_T], __start: Optional[int], __stop: Optional[int], __step: Optional[int] = ...
    ) -> None: ...
    def __iter__(self) -> Iterator[_T]: ...
    def __next__(self) -> _T: ...

class starmap(Iterator[_T], Generic[_T]):
    def __init__(self, __function: Callable[..., _T], __iterable: Iterable[Iterable[Any]]) -> None: ...
    def __iter__(self) -> Iterator[_T]: ...
    def __next__(self) -> _T: ...

class takewhile(Iterator[_T], Generic[_T]):
    def __init__(self, __predicate: Predicate[_T], __iterable: Iterable[_T]) -> None: ...
    def __iter__(self) -> Iterator[_T]: ...
    def __next__(self) -> _T: ...

def tee(__iterable: Iterable[_T], __n: int = ...) -> Tuple[Iterator[_T], ...]: ...

class zip_longest(Iterator[Any]):
    def __init__(self, *p: Iterable[Any], fillvalue: Any = ...) -> None: ...
    def __iter__(self) -> Iterator[Any]: ...
    def __next__(self) -> Any: ...

_T3 = TypeVar("_T3")
_T4 = TypeVar("_T4")
_T5 = TypeVar("_T5")
_T6 = TypeVar("_T6")

class product(Iterator[_T_co], Generic[_T_co]):
    @overload
    def __new__(cls, __iter1: Iterable[_T1]) -> product[Tuple[_T1]]: ...
    @overload
    def __new__(cls, __iter1: Iterable[_T1], __iter2: Iterable[_T2]) -> product[Tuple[_T1, _T2]]: ...
    @overload
    def __new__(cls, __iter1: Iterable[_T1], __iter2: Iterable[_T2], __iter3: Iterable[_T3]) -> product[Tuple[_T1, _T2, _T3]]: ...
    @overload
    def __new__(
        cls, __iter1: Iterable[_T1], __iter2: Iterable[_T2], __iter3: Iterable[_T3], __iter4: Iterable[_T4]
    ) -> product[Tuple[_T1, _T2, _T3, _T4]]: ...
    @overload
    def __new__(
        cls,
        __iter1: Iterable[_T1],
        __iter2: Iterable[_T2],
        __iter3: Iterable[_T3],
        __iter4: Iterable[_T4],
        __iter5: Iterable[_T5],
    ) -> product[Tuple[_T1, _T2, _T3, _T4, _T5]]: ...
    @overload
    def __new__(
        cls,
        __iter1: Iterable[_T1],
        __iter2: Iterable[_T2],
        __iter3: Iterable[_T3],
        __iter4: Iterable[_T4],
        __iter5: Iterable[_T5],
        __iter6: Iterable[_T6],
    ) -> product[Tuple[_T1, _T2, _T3, _T4, _T5, _T6]]: ...
    @overload
    def __new__(
        cls,
        __iter1: Iterable[Any],
        __iter2: Iterable[Any],
        __iter3: Iterable[Any],
        __iter4: Iterable[Any],
        __iter5: Iterable[Any],
        __iter6: Iterable[Any],
        __iter7: Iterable[Any],
        *iterables: Iterable[Any],
    ) -> product[Tuple[Any, ...]]: ...
    @overload
    def __new__(cls, *iterables: Iterable[_T1], repeat: int) -> product[Tuple[_T1, ...]]: ...
    @overload
    def __new__(cls, *iterables: Iterable[Any], repeat: int = ...) -> product[Tuple[Any, ...]]: ...
    def __iter__(self) -> Iterator[_T_co]: ...
    def __next__(self) -> _T_co: ...

class permutations(Iterator[Tuple[_T, ...]], Generic[_T]):
    def __init__(self, iterable: Iterable[_T], r: Optional[int] = ...) -> None: ...
    def __iter__(self) -> Iterator[Tuple[_T, ...]]: ...
    def __next__(self) -> Tuple[_T, ...]: ...

class combinations(Iterator[_T_co], Generic[_T_co]):
    @overload
    def __new__(cls, iterable: Iterable[_T], r: Literal[2]) -> combinations[Tuple[_T, _T]]: ...
    @overload
    def __new__(cls, iterable: Iterable[_T], r: Literal[3]) -> combinations[Tuple[_T, _T, _T]]: ...
    @overload
    def __new__(cls, iterable: Iterable[_T], r: Literal[4]) -> combinations[Tuple[_T, _T, _T, _T]]: ...
    @overload
    def __new__(cls, iterable: Iterable[_T], r: Literal[5]) -> combinations[Tuple[_T, _T, _T, _T, _T]]: ...
    @overload
    def __new__(cls, iterable: Iterable[_T], r: int) -> combinations[Tuple[_T, ...]]: ...
    def __iter__(self) -> Iterator[_T_co]: ...
    def __next__(self) -> _T_co: ...

class combinations_with_replacement(Iterator[Tuple[_T, ...]], Generic[_T]):
    def __init__(self, iterable: Iterable[_T], r: int) -> None: ...
    def __iter__(self) -> Iterator[Tuple[_T, ...]]: ...
    def __next__(self) -> Tuple[_T, ...]: ...

if sys.version_info >= (3, 10):
    class pairwise(Iterator[_T_co], Generic[_T_co]):
        def __new__(cls, __iterable: Iterable[_T]) -> pairwise[Tuple[_T, _T]]: ...
        def __iter__(self) -> Iterator[_T_co]: ...
        def __next__(self) -> _T_co: ...
