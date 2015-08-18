# NOTE: These are incomplete!

from typing import Dict, Generic, TypeVar, Iterable, Tuple, Callable, Mapping, overload

# namedtuple is special-cased in the type checker; the initializer is ignored.
namedtuple = object()

# TODO
class MutableMapping(object):
    pass

# TODO
class OrderedDict(object):
    pass

_KT = TypeVar('_KT')
_VT = TypeVar('_VT')

class defaultdict(Dict[_KT, _VT], Generic[_KT, _VT]):
    default_factory = ...  # type: Callable[[], _VT]

    @overload
    def __init__(self) -> None: ...
    @overload
    def __init__(self, map: Mapping[_KT, _VT]) -> None: ...
    @overload
    def __init__(self, iterable: Iterable[Tuple[_KT, _VT]]) -> None: ...
    @overload
    def __init__(self, default_factory: Callable[[], _VT]) -> None: ...
    @overload
    def __init__(self, default_factory: Callable[[], _VT],
                 map: Mapping[_KT, _VT]) -> None: ...
    @overload
    def __init__(self, default_factory: Callable[[], _VT],
                 iterable: Iterable[Tuple[_KT, _VT]]) -> None: ...
    # TODO __init__ keyword args

    def __missing__(self, key: _KT) -> _VT: ...
    # TODO __reversed__
