# Minimal typing fixture for disallow-str-iteration tests.

from abc import ABCMeta, abstractmethod

Any = object()
TypeVar = 0
Generic = 0
Protocol = 0
overload = 0

_T = TypeVar("_T")
_KT = TypeVar("_KT")
_T_co = TypeVar("_T_co", covariant=True)
_VT_co = TypeVar("_VT_co", covariant=True)  # Value type covariant containers.
_TC = TypeVar("_TC", bound=type[object])

@runtime_checkable
class Iterable(Protocol[_T_co]):
    @abstractmethod
    def __iter__(self) -> Iterator[_T_co]: ...

@runtime_checkable
class Iterator(Iterable[_T_co], Protocol[_T_co]):
    @abstractmethod
    def __next__(self) -> _T_co: ...
    def __iter__(self) -> Iterator[_T_co]: ...

@runtime_checkable
class Reversible(Iterable[_T_co], Protocol[_T_co]):
    @abstractmethod
    def __reversed__(self) -> Iterator[_T_co]: ...

@runtime_checkable
class Container(Protocol[_T_co]):
    # This is generic more on vibes than anything else
    @abstractmethod
    def __contains__(self, x: object, /) -> bool: ...

@runtime_checkable
class Collection(Iterable[_T_co], Container[_T_co], Protocol[_T_co]):
    # Implement Sized (but don't have it as a base class).
    @abstractmethod
    def __len__(self) -> int: ...

class Sequence(Reversible[_T_co], Collection[_T_co]):
    @overload
    @abstractmethod
    def __getitem__(self, index: int) -> _T_co: ...
    @overload
    @abstractmethod
    def __getitem__(self, index: slice) -> Sequence[_T_co]: ...
    def __contains__(self, value: object) -> bool: ...
    def __iter__(self) -> Iterator[_T_co]: ...
    def __reversed__(self) -> Iterator[_T_co]: ...

class Mapping(Collection[_KT], Generic[_KT, _VT_co]):
    @abstractmethod
    def __getitem__(self, key: _KT, /) -> _VT_co: ...
    def __contains__(self, key: object, /) -> bool: ...

def runtime_checkable(cls: _TC) -> _TC:
    return cls
