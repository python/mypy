TypeVar = 0
Generic = 0
Any = 0
overload = 0
Type = 0
NewType = 0
Optional = 0
Union = 0
cast = 0

T_co = TypeVar('T_co', covariant=True)
KT = TypeVar('KT')

class Iterable(Generic[T_co]): pass
class Iterator(Iterable[T_co]):
    def __next__(self) -> T_co: pass
class Sequence(Iterable[T_co]): pass
class Mapping(Iterable[KT], Generic[KT, T_co]): pass

class List(Sequence[KT]):
    def __iter__(self) -> Iterator[KT]: pass

class Tuple(Sequence): pass
class NamedTuple(Tuple):
    _source: str
    @overload
    def __init__(self, typename: str, fields: Iterable[Tuple[str, object]] = ...) -> None: ...
    @overload
    def __init__(self, typename: str, fields: None = ..., **kwargs: object) -> None: ...
