# Stubs for weakref

# NOTE: These are incomplete!

from typing import (
    typevar, Generic, Any, Function, overload, Mapping, Iterator, Dict, Tuple,
    Iterable
)

_T = typevar('_T')
_KT = typevar('_KT')
_VT = typevar('_VT')

class ReferenceType(Generic[_T]):
    # TODO members
    pass

def ref(o: _T, callback: Function[[ReferenceType[_T]],
                                 Any] = None) -> ReferenceType[_T]: pass

# TODO callback
def proxy(object: _T) -> _T: pass

class WeakValueDictionary(Generic[_KT, _VT]):
    # TODO tuple iterable argument?
    @overload
    def __init__(self) -> None: pass
    @overload
    def __init__(self, map: Mapping[_KT, _VT]) -> None: pass

    def __len__(self) -> int: pass
    def __getitem__(self, k: _KT) -> _VT: pass
    def __setitem__(self, k: _KT, v: _VT) -> None: pass
    def __delitem__(self, v: _KT) -> None: pass
    def __contains__(self, o: object) -> bool: pass
    def __iter__(self) -> Iterator[_KT]: pass
    def __str__(self) -> str: pass

    def clear(self) -> None: pass
    def copy(self) -> Dict[_KT, _VT]: pass

    @overload
    def get(self, k: _KT) -> _VT: pass
    @overload
    def get(self, k: _KT, default: _VT) -> _VT: pass

    @overload
    def pop(self, k: _KT) -> _VT: pass
    @overload
    def pop(self, k: _KT, default: _VT) -> _VT: pass

    def popitem(self) -> Tuple[_KT, _VT]: pass

    @overload
    def setdefault(self, k: _KT) -> _VT: pass
    @overload
    def setdefault(self, k: _KT, default: _VT) -> _VT: pass

    @overload
    def update(self, m: Mapping[_KT, _VT]) -> None: pass
    @overload
    def update(self, m: Iterable[Tuple[_KT, _VT]]) -> None: pass

    # NOTE: incompatible with Mapping
    def keys(self) -> Iterator[_KT]: pass
    def values(self) -> Iterator[_VT]: pass
    def items(self) -> Iterator[Tuple[_KT, _VT]]: pass

    # TODO return type
    def valuerefs(self) -> Iterable[Any]: pass
