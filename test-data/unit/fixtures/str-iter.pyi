# Builtins stub used in disallow-str-iteration tests.


from typing import Generic, Iterator, Mapping, Sequence, TypeVar, overload

_T = TypeVar("_T")
_KT = TypeVar("_KT")
_VT = TypeVar("_VT")

class object:
    def __init__(self) -> None: pass

class type: pass
class int: pass
class bool(int): pass
class ellipsis: pass
class slice: pass

class str(Sequence[str]):
    def __iter__(self) -> Iterator[str]: pass
    def __len__(self) -> int: pass
    def __contains__(self, item: object) -> bool: pass
    @overload
    def __getitem__(self, i: int, /) -> str: ...
    @overload
    def __getitem__(self, s: slice, /) -> Sequence[str]: ...

class list(Sequence[_T], Generic[_T]):
    def __iter__(self) -> Iterator[_T]: pass
    def __len__(self) -> int: pass
    def __contains__(self, item: object) -> bool: pass
    @overload
    def __getitem__(self, i: int, /) -> _T: ...
    @overload
    def __getitem__(self, s: slice, /) -> list[_T]: ...

class tuple(Sequence[_T], Generic[_T]):
    def __iter__(self) -> Iterator[_T]: pass
    def __len__(self) -> int: pass
    def __contains__(self, item: object) -> bool: pass
    @overload
    def __getitem__(self, i: int, /) -> _T: ...
    @overload
    def __getitem__(self, s: slice, /) -> list[_T]: ...

class dict(Mapping[_KT, _VT], Generic[_KT, _VT]):
    def __iter__(self) -> Iterator[_KT]: pass
    def __len__(self) -> int: pass
    def __contains__(self, item: object) -> bool: pass
    def __getitem__(self, key: _KT) -> _VT: pass

def isinstance(x: object, t: type) -> bool: pass
