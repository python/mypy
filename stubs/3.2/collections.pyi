# Stubs for collections

# Based on http://docs.python.org/3.2/library/collections.html

# TODO namedtuple (requires language changes)
# TODO UserDict
# TODO UserList
# TODO UserString
# TODO more abstract base classes (interfaces in mypy)

from typing import (
    typevar, Iterable, AbstractGeneric, Iterator, Dict, Generic, overload,
    Mapping, List, Tuple, Undefined, Function, Set, Sequence, Sized
)

_T = typevar('_T')
_KT = typevar('_KT')
_VT = typevar('_VT')


class deque(Sized, Iterable[_T], AbstractGeneric[_T]):
    # TODO int with None default
    maxlen = 0 # TODO readonly
    def __init__(self, iterable: Iterable[_T] = None,
                 maxlen: int = None) -> None: pass
    def append(self, x: _T) -> None: pass
    def appendleft(self, x: _T) -> None: pass
    def clear(self) -> None: pass
    def count(self, x: _T) -> int: pass
    def extend(self, iterable: Iterable[_T]) -> None: pass
    def extendleft(self, iterable: Iterable[_T]) -> None: pass
    def pop(self) -> _T: pass
    def popleft(self) -> _T: pass
    def remove(self, value: _T) -> None: pass
    def reverse(self) -> None: pass
    def rotate(self, n: int) -> None: pass

    def __len__(self) -> int: pass
    def __iter__(self) -> Iterator[_T]: pass
    def __str__(self) -> str: pass
    def __hash__(self) -> int: pass

    def __getitem__(self, i: int) -> _T: pass
    def __setitem__(self, i: int, x: _T) -> None: pass
    def __contains__(self, o: _T) -> bool: pass

    # TODO __reversed__


class Counter(Dict[_T, int], Generic[_T]):
    @overload
    def __init__(self) -> None: pass
    @overload
    def __init__(self, Mapping: Mapping[_T, int]) -> None: pass
    @overload
    def __init__(self, iterable: Iterable[_T]) -> None: pass
    # TODO keyword arguments

    def elements(self) -> Iterator[_T]: pass

    @overload
    def most_common(self) -> List[_T]: pass
    @overload
    def most_common(self, n: int) -> List[_T]: pass

    @overload
    def subtract(self, Mapping: Mapping[_T, int]) -> None: pass
    @overload
    def subtract(self, iterable: Iterable[_T]) -> None: pass

    # TODO update


class OrderedDict(Dict[_KT, _VT], Generic[_KT, _VT]):
    def popitem(self, last: bool = True) -> Tuple[_KT, _VT]: pass
    def move_to_end(self, key: _KT, last: bool = True) -> None: pass


class defaultdict(Dict[_KT, _VT], Generic[_KT, _VT]):
    default_factory = Undefined(Function[[], _VT])

    @overload
    def __init__(self) -> None: pass
    @overload
    def __init__(self, map: Mapping[_KT, _VT]) -> None: pass
    @overload
    def __init__(self, iterable: Iterable[Tuple[_KT, _VT]]) -> None: pass
    @overload
    def __init__(self, default_factory: Function[[], _VT]) -> None: pass
    @overload
    def __init__(self, default_factory: Function[[], _VT],
                 map: Mapping[_KT, _VT]) -> None: pass
    @overload
    def __init__(self, default_factory: Function[[], _VT],
                 iterable: Iterable[Tuple[_KT, _VT]]) -> None: pass
    # TODO __init__ keyword args

    def __missing__(self, key: _KT) -> _VT: pass
    # TODO __reversed__
