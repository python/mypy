TypeVar = 0
Generic = 0
Any = 0
overload = 0
Type = 0
Literal = 0

T_co = TypeVar('T_co', covariant=True)
KT = TypeVar('KT')

class Iterable(Generic[T_co]): pass
class Iterator(Iterable[T_co]): pass
class Sequence(Iterable[T_co]): pass
class Mapping(Iterable[KT], Generic[KT, T_co]): pass

class Tuple(Sequence): pass
class NamedTuple(Tuple):
    name: str
