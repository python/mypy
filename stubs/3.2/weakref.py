# Stubs for weakref

# NOTE: These are incomplete!

from typing import (
    typevar, Generic, Any, Function, overload, Mapping, Iterator, Dict, Tuple,
    Iterable
)

T = typevar('T')
KT = typevar('KT')
VT = typevar('VT')

class ReferenceType(Generic[T]):
    # TODO members
    pass

def ref(o: T, callback: Function[[ReferenceType[T]],
                                 Any] = None) -> ReferenceType[T]: pass

# TODO callback
def proxy(object: T) -> T: pass

class WeakValueDictionary(Generic[KT, VT]):
    # TODO tuple iterable argument?
    @overload
    def __init__(self) -> None: pass
    @overload
    def __init__(self, map: Mapping[KT, VT]) -> None: pass

    def __len__(self) -> int: pass
    def __getitem__(self, k: KT) -> VT: pass
    def __setitem__(self, k: KT, v: VT) -> None: pass
    def __delitem__(self, v: KT) -> None: pass
    def __contains__(self, o: object) -> bool: pass
    def __iter__(self) -> Iterator[KT]: pass
    def __str__(self) -> str: pass

    def clear(self) -> None: pass
    def copy(self) -> Dict[KT, VT]: pass

    @overload
    def get(self, k: KT) -> VT: pass
    @overload
    def get(self, k: KT, default: VT) -> VT: pass

    @overload
    def pop(self, k: KT) -> VT: pass
    @overload
    def pop(self, k: KT, default: VT) -> VT: pass

    def popitem(self) -> Tuple[KT, VT]: pass

    @overload
    def setdefault(self, k: KT) -> VT: pass
    @overload
    def setdefault(self, k: KT, default: VT) -> VT: pass

    @overload
    def update(self, m: Mapping[KT, VT]) -> None: pass
    @overload
    def update(self, m: Iterable[Tuple[KT, VT]]) -> None: pass

    # NOTE: incompatible with Mapping
    def keys(self) -> Iterator[KT]: pass
    def values(self) -> Iterator[VT]: pass
    def items(self) -> Iterator[Tuple[KT, VT]]: pass

    # TODO return type
    def valuerefs(self) -> Iterable[Any]: pass
