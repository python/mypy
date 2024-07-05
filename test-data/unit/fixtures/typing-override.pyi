TypeVar = 0
Generic = 0
Any = object()
overload = 0
Type = 0
Literal = 0
Optional = 0
Self = 0
Tuple = 0
ClassVar = 0
Callable = 0

T = TypeVar('T')
T_co = TypeVar('T_co', covariant=True)
KT = TypeVar('KT')

class Iterable(Generic[T_co]): pass
class Iterator(Iterable[T_co]): pass
class Sequence(Iterable[T_co]): pass
class Mapping(Iterable[KT], Generic[KT, T_co]):
    def keys(self) -> Iterable[T]: pass  # Approximate return type
    def __getitem__(self, key: T) -> T_co: pass

def override(__arg: T) -> T: ...

class _SpecialForm: pass
