TypeVar = 0
Generic = 0
Any = 0
overload = 0
Type = 0

T_co = TypeVar('T_co', covariant=True)

class Iterable(Generic[T_co]): pass
class Iterator(Iterable[T_co]): pass
class Sequence(Iterable[T_co]): pass

class Tuple(Sequence): pass
class NamedTuple(Tuple): pass

class str: pass
class int: pass
