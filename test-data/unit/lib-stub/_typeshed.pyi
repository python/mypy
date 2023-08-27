from typing import Protocol, TypeVar, Iterable

_KT = TypeVar("_KT")
_VT_co = TypeVar("_VT_co", covariant=True)

class SupportsKeysAndGetItem(Protocol[_KT, _VT_co]):
    def keys(self) -> Iterable[_KT]: pass
    def __getitem__(self, __key: _KT) -> _VT_co: pass
