"""Static type checking helpers"""

from abc import ABCMeta, abstractmethod, abstractproperty
import collections
import inspect
import sys
import re
import functools


__all__ = [
    # Type system related
    'Any',
    'AnyStr',
    'Dict',
    'Callable',
    'Generic',
    'GenericMeta',
    'IO',
    'List',
    'Match',
    'NamedTuple',
    'Optional',
    'Pattern',
    'Set',
    'Tuple',
    'Undefined',
    'Union',
    'cast',
    'forwardref',
    'overload',
    'TypeVar',
    # Protocols and abstract base classes
    'Container',
    'Iterable',
    'Iterator',
    'Sequence',
    'Sized',
    'AbstractSet',
    'Mapping',
    'BinaryIO',
    'TextIO',
]


def builtinclass(cls):
    """Mark a class as a built-in/extension class for type checking."""
    return cls


def ducktype(type):
    """Return a duck type declaration decorator.

    The decorator only affects type checking.
    """
    def decorator(cls):
        return cls
    return decorator


def disjointclass(type):
    """Return a disjoint class declaration decorator.

    The decorator only affects type checking.
    """
    def decorator(cls):
        return cls
    return decorator


class GenericMeta(ABCMeta):
    """Metaclass for (abstract) generic classes that support type indexing.

    This is used for both ABCs and ordinary classes.
    """

    def __new__(mcls, name, bases, namespace):
        cls = super().__new__(mcls, name, bases, namespace)
        # 'Protocol' must be an explicit base class in order for a class to
        # be a protocol.
        cls._is_protocol = name == '_Protocol' or _Protocol in bases
        return cls

    def __getitem__(self, args):
        # Just ignore args; they are for compile-time checks only.
        return self


class _Protocol(metaclass=GenericMeta):
    """Internal base class for protocol classes (structural isinstance checks)."""

    @classmethod
    def __subclasshook__(cls, c):
        if not cls._is_protocol:
            # No structural checks since this isn't a protocol.
            return NotImplemented

        if cls is _Protocol:
            # Every class is a subclass of the empty protocol.
            return True

        # Find all attributes defined in the protocol.
        attrs = cls._get_protocol_attrs()

        for attr in attrs:
            if not any(attr in d.__dict__ for d in c.__mro__):
                return NotImplemented
        return True

    @classmethod
    def _get_protocol_attrs(cls):
        # Get all Protocol base classes.
        protocol_bases = []
        for c in cls.__mro__:
            if getattr(c, '_is_protocol', False) and c.__name__ != '_Protocol':
                protocol_bases.append(c)

        # Get attributes included in protocol.
        attrs = set()
        for base in protocol_bases:
            for attr in base.__dict__.keys():
                # Include attributes not defined in any non-protocol bases.
                for c in cls.__mro__:
                    if (c is not base and attr in c.__dict__ and
                            not getattr(c, '_is_protocol', False)):
                        break
                else:
                    if (not attr.startswith('_abc_') and
                        attr != '__abstractmethods__' and
                        attr != '_is_protocol' and
                        attr != '__dict__' and
                        attr != '_get_protocol_attrs' and
                        attr != '__module__'):
                        attrs.add(attr)

        return attrs


class Generic(metaclass=GenericMeta):
    """Base class for (abstract) generic classes."""


class TypeAlias:
    """Class for defining generic aliases for library types."""

    def __init__(self, target_type):
        self.target_type = target_type

    def __getitem__(self, typeargs):
        return self.target_type


Traceback = object()  # TODO proper type object


# Define aliases for built-in types that support indexing.
List = TypeAlias(list)
Dict = TypeAlias(dict)
Set = TypeAlias(set)
Tuple = TypeAlias(tuple)
Callable = TypeAlias(callable)
Pattern = TypeAlias(type(re.compile('')))
Match = TypeAlias(type(re.match('', '')))


def union(x): return x


Union = TypeAlias(union)


class _Optional:
    def __getitem__(self, typearg):
        return Union[typearg, None]


Optional = _Optional()


def NamedTuple(typename, fields):
    return collections.namedtuple(typename,
                                  (name for name, type in fields))


class TypeVar:
    def __init__(self, name, *values):
        self.name = name
        if not values:
            values = None
        self.values = values


# Predefined type variables.
AnyStr = TypeVar('AnyStr', str, bytes)


class forwardref:
    def __init__(self, name):
        self.name = name


def Any(x):
    """The Any type; can also be used to cast a value to type Any."""
    return x

def cast(type, object):
    """Cast a value to a type.

    This only affects static checking; simply return object at runtime.
    """
    return object


def overload(func):
    raise RuntimeError("Overloading only supported in library stubs")


class Undefined:
    """Class that represents an undefined value with a specified type.

    At runtime the name Undefined is bound to an instance of this
    class.  The intent is that any operation on an Undefined object
    raises an exception, including use in a boolean context.  Some
    operations cannot be disallowed: Undefined can be used as an
    operand of 'is', and it can be assigned to variables and stored in
    containers.

    'Undefined' makes it possible to declare the static type of a
    variable even if there is no useful default value to initialize it
    with:

      from typing import Undefined
      x = Undefined(int)
      y = Undefined # type: int

    The latter form can be used if efficiency is of utmost importance,
    since it saves a call operation and potentially additional
    operations needed to evaluate a type expression.  Undefined(x)
    just evaluates to Undefined, ignoring the argument value.
    """

    def __repr__(self):
        return '<typing.Undefined>'

    def __setattr__(self, attr, value):
        raise AttributeError("'Undefined' object has no attribute '%s'" % attr)

    def __eq__(self, other):
        raise TypeError("'Undefined' object cannot be compared")

    def __call__(self, type):
        return self

    def __bool__(self):
        raise TypeError("'Undefined' object is not valid as a boolean")


Undefined = Undefined()


# Abstract classes


T = TypeVar('T')
KT = TypeVar('KT')
VT = TypeVar('VT')


class SupportsInt(_Protocol):
    @abstractmethod
    def __int__(self) -> int: pass


class SupportsFloat(_Protocol):
    @abstractmethod
    def __float__(self) -> float: pass


class SupportsAbs(_Protocol[T]):
    @abstractmethod
    def __abs__(self) -> T: pass


class SupportsRound(_Protocol[T]):
    @abstractmethod
    def __round__(self, ndigits: int = 0) -> T: pass


class Reversible(_Protocol[T]):
    @abstractmethod
    def __reversed__(self) -> 'Iterator[T]': pass


class Sized(_Protocol):
    @abstractmethod
    def __len__(self) -> int: pass


class Container(_Protocol[T]):
    @abstractmethod
    def __contains__(self, x) -> bool: pass


class Iterable(_Protocol[T]):
    @abstractmethod
    def __iter__(self) -> 'Iterator[T]': pass


class Iterator(Iterable[T], _Protocol[T]):
    @abstractmethod
    def __next__(self) -> T: pass


class Sequence(Sized, Iterable[T], Container[T], Generic[T]):
    @abstractmethod
    def __getitem__(self, x): pass

    @abstractmethod
    def __reversed__(self, s: slice) -> Iterator[T]: pass

    @abstractmethod
    def index(self, x) -> int: pass

    @abstractmethod
    def count(self, x) -> int: pass


for t in list, tuple, str, bytes, range:
    Sequence.register(t)


class AbstractSet(Sized, Iterable[T], Generic[T]):
    @abstractmethod
    def __contains__(self, x: object) -> bool: pass
    @abstractmethod
    def __and__(self, s: 'AbstractSet[T]') -> 'AbstractSet[T]': pass
    @abstractmethod
    def __or__(self, s: 'AbstractSet[T]') -> 'AbstractSet[T]': pass
    @abstractmethod
    def __sub__(self, s: 'AbstractSet[T]') -> 'AbstractSet[T]': pass
    @abstractmethod
    def __xor__(self, s: 'AbstractSet[T]') -> 'AbstractSet[T]': pass
    @abstractmethod
    def isdisjoint(self, s: 'AbstractSet[T]') -> bool: pass


for t in set, frozenset, type({}.keys()), type({}.items()):
    AbstractSet.register(t)


class Mapping(Sized, Iterable[KT], Generic[KT, VT]):
    @abstractmethod
    def __getitem__(self, k: KT) -> VT: pass
    @abstractmethod
    def __setitem__(self, k: KT, v: VT) -> None: pass
    @abstractmethod
    def __delitem__(self, v: KT) -> None: pass
    @abstractmethod
    def __contains__(self, o: object) -> bool: pass

    @abstractmethod
    def clear(self) -> None: pass
    @abstractmethod
    def copy(self) -> 'Mapping[KT, VT]': pass
    @abstractmethod
    def get(self, k): pass
    @abstractmethod
    def pop(self, k, default=None): pass
    @abstractmethod
    def popitem(self) -> Tuple[KT, VT]: pass
    @abstractmethod
    def setdefault(self, k, default=None): pass
    @abstractmethod
    def update(self, m: Union['Mapping[KT, VT]', Iterable[Tuple[KT, VT]]]) -> None: pass
    @abstractmethod
    def keys(self) -> AbstractSet[KT]: pass
    @abstractmethod
    def values(self) -> AbstractSet[VT]: pass
    @abstractmethod
    def items(self) -> AbstractSet[Tuple[KT, VT]]: pass


# TODO Consider more types: os.environ, etc. However, these add dependencies.
Mapping.register(dict)


# Note that the BinaryIO and TextIO classes must be in sync with typing module
# stubs.


class IO(Generic[AnyStr]):
    @abstractproperty
    def mode(self) -> str: pass
    @abstractproperty
    def name(self) -> str: pass
    @abstractmethod
    def close(self) -> None: pass
    @abstractmethod
    def closed(self) -> bool: pass
    @abstractmethod
    def fileno(self) -> int: pass
    @abstractmethod
    def flush(self) -> None: pass
    @abstractmethod
    def isatty(self) -> bool: pass
    @abstractmethod
    def read(self, n: int = -1) -> AnyStr: pass
    @abstractmethod
    def readable(self) -> bool: pass
    @abstractmethod
    def readline(self, limit: int = -1) -> AnyStr: pass
    @abstractmethod
    def readlines(self, hint: int = -1) -> List[AnyStr]: pass
    @abstractmethod
    def seek(self, offset: int, whence: int = 0) -> int: pass
    @abstractmethod
    def seekable(self) -> bool: pass
    @abstractmethod
    def tell(self) -> int: pass
    @abstractmethod
    def truncate(self, size: int = None) -> int: pass
    @abstractmethod
    def writable(self) -> bool: pass
    @abstractmethod
    def write(self, s: AnyStr) -> int: pass
    @abstractmethod
    def writelines(self, lines: List[AnyStr]) -> None: pass

    @abstractmethod
    def __enter__(self) -> 'IO[AnyStr]': pass
    @abstractmethod
    def __exit__(self, type, value, traceback) -> None: pass


class BinaryIO(IO[bytes]):
    @abstractmethod
    def write(self, s: Union[bytes, bytearray]) -> int: pass
    @abstractmethod
    def __enter__(self) -> 'BinaryIO': pass


class TextIO(IO[str]):
    @abstractproperty
    def buffer(self) -> BinaryIO: pass
    @abstractproperty
    def encoding(self) -> str: pass
    @abstractproperty
    def errors(self) -> str: pass
    @abstractproperty
    def line_buffering(self) -> bool: pass
    @abstractproperty
    def newlines(self) -> Any: pass
    @abstractmethod
    def __enter__(self) -> 'TextIO': pass


# TODO Register IO/TextIO/BinaryIO as the base class of file-like types.


del t
