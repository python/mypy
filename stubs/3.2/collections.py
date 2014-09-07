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

T = typevar('T')
KT = typevar('KT')
VT = typevar('VT')


class deque(Sized, Iterable[T], AbstractGeneric[T]):
    # TODO int with None default
    maxlen = 0 # TODO readonly
    def __init__(self, iterable: Iterable[T] = None,
                 maxlen: int = None) -> None: pass
    def append(self, x: T) -> None: pass
    def appendleft(self, x: T) -> None: pass
    def clear(self) -> None: pass
    def count(self, x: T) -> int: pass
    def extend(self, iterable: Iterable[T]) -> None: pass
    def extendleft(self, iterable: Iterable[T]) -> None: pass
    def pop(self) -> T: pass
    def popleft(self) -> T: pass
    def remove(self, value: T) -> None: pass
    def reverse(self) -> None: pass
    def rotate(self, n: int) -> None: pass

    def __len__(self) -> int: pass
    def __iter__(self) -> Iterator[T]: pass
    def __str__(self) -> str: pass
    def __hash__(self) -> int: pass

    def __getitem__(self, i: int) -> T: pass
    def __setitem__(self, i: int, x: T) -> None: pass
    def __contains__(self, o: T) -> bool: pass

    # TODO __reversed__


class Counter(Dict[T, int], Generic[T]):
    @overload
    def __init__(self) -> None: pass
    @overload
    def __init__(self, Mapping: Mapping[T, int]) -> None: pass
    @overload
    def __init__(self, iterable: Iterable[T]) -> None: pass
    # TODO keyword arguments

    def elements(self) -> Iterator[T]: pass

    @overload
    def most_common(self) -> List[T]: pass
    @overload
    def most_common(self, n: int) -> List[T]: pass

    @overload
    def subtract(self, Mapping: Mapping[T, int]) -> None: pass
    @overload
    def subtract(self, iterable: Iterable[T]) -> None: pass

    # TODO update


class OrderedDict(Dict[KT, VT], Generic[KT, VT]):
    def popitem(self, last: bool = True) -> Tuple[KT, VT]: pass
    def move_to_end(self, key: KT, last: bool = True) -> None: pass


class defaultdict(Dict[KT, VT], Generic[KT, VT]):
    default_factory = Undefined(Function[[], VT])

    @overload
    def __init__(self) -> None: pass
    @overload
    def __init__(self, map: Mapping[KT, VT]) -> None: pass
    @overload
    def __init__(self, iterable: Iterable[Tuple[KT, VT]]) -> None: pass
    @overload
    def __init__(self, default_factory: Function[[], VT]) -> None: pass
    @overload
    def __init__(self, default_factory: Function[[], VT],
                 map: Mapping[KT, VT]) -> None: pass
    @overload
    def __init__(self, default_factory: Function[[], VT],
                 iterable: Iterable[Tuple[KT, VT]]) -> None: pass
    # TODO __init__ keyword args

    def __missing__(self, key: KT) -> VT: pass
    # TODO __reversed__
