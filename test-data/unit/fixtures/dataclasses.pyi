import _typeshed
from typing import (
    Generic, Iterator, Iterable, Mapping, Optional, Sequence, Tuple,
    TypeVar, Union, overload,
)
from typing_extensions import override

_T = TypeVar('_T')
_U = TypeVar('_U')
KT = TypeVar('KT')
VT = TypeVar('VT')

class object:
    def __init__(self) -> None: pass
    def __init_subclass__(cls) -> None: pass
    def __eq__(self, o: object) -> bool: pass
    def __ne__(self, o: object) -> bool: pass

class type: pass
class ellipsis: pass
class tuple(Generic[_T]): pass
class int: pass
class float: pass
class bytes: pass
class str: pass
class bool(int): pass

class dict(Mapping[KT, VT]):
    @overload
    def __init__(self, **kwargs: VT) -> None: pass
    @overload
    def __init__(self, arg: Iterable[Tuple[KT, VT]], **kwargs: VT) -> None: pass
    @override
    def __getitem__(self, key: KT) -> VT: pass
    def __setitem__(self, k: KT, v: VT) -> None: pass
    @override
    def __iter__(self) -> Iterator[KT]: pass
    def __contains__(self, item: object) -> int: pass
    def update(self, a: Mapping[KT, VT]) -> None: pass
    @overload
    def get(self, k: KT) -> Optional[VT]: pass
    @overload
    def get(self, k: KT, default: Union[KT, _T]) -> Union[VT, _T]: pass
    def __len__(self) -> int: ...

class list(Generic[_T], Sequence[_T]):
    def __contains__(self, item: object) -> int: pass
    @override
    def __getitem__(self, key: int) -> _T: pass
    @override
    def __iter__(self) -> Iterator[_T]: pass

class function: pass
class classmethod: pass
class staticmethod: pass
property = object()
