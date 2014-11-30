"""Static type checking helpers"""

from abc import ABCMeta, abstractmethod, abstractproperty
import collections
import inspect
import sys
import re


__all__ = [
    # Type system related
    'AbstractGeneric',
    'AbstractGenericMeta',
    'Any',
    'AnyStr',
    'Dict',
    'Function',
    'Generic',
    'GenericMeta',
    'IO',
    'List',
    'Match',
    'NamedTuple',
    'Pattern',
    'Protocol',
    'Set',
    'Tuple',
    'Undefined',
    'Union',
    'cast',
    'forwardref',
    'overload',
    'typevar',
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


class GenericMeta(type):
    """Metaclass for generic classes that support indexing by types."""

    def __getitem__(self, args):
        # Just ignore args; they are for compile-time checks only.
        return self


class Generic(metaclass=GenericMeta):
    """Base class for generic classes."""


class AbstractGenericMeta(ABCMeta):
    """Metaclass for abstract generic classes that support type indexing.

    This is used for both protocols and ordinary abstract classes.
    """

    def __new__(mcls, name, bases, namespace):
        cls = super().__new__(mcls, name, bases, namespace)
        # 'Protocol' must be an explicit base class in order for a class to
        # be a protocol.
        cls._is_protocol = name == 'Protocol' or Protocol in bases
        return cls

    def __getitem__(self, args):
        # Just ignore args; they are for compile-time checks only.
        return self


class Protocol(metaclass=AbstractGenericMeta):
    """Base class for protocol classes."""

    @classmethod
    def __subclasshook__(cls, c):
        if not cls._is_protocol:
            # No structural checks since this isn't a protocol.
            return NotImplemented

        if cls is Protocol:
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
            if getattr(c, '_is_protocol', False) and c.__name__ != 'Protocol':
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


class AbstractGeneric(metaclass=AbstractGenericMeta):
    """Base class for abstract generic classes."""


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
Function = TypeAlias(callable)
Pattern = TypeAlias(type(re.compile('')))
Match = TypeAlias(type(re.match('', '')))


def union(x): return x


Union = TypeAlias(union)


def NamedTuple(typename, fields):
    return collections.namedtuple(typename,
                                  (name for name, type in fields))


class typevar:
    def __init__(self, name, *, values=None):
        self.name = name
        self.values = values


# Predefined type variables.
AnyStr = typevar('AnyStr', values=(str, bytes))


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
    """Function decorator for defining overloaded functions."""
    frame = sys._getframe(1)
    locals = frame.f_locals
    # See if there is a previous overload variant available.  Also verify
    # that the existing function really is overloaded: otherwise, replace
    # the definition.  The latter is actually important if we want to reload
    # a library module such as genericpath with a custom one that uses
    # overloading in the implementation.
    if func.__name__ in locals and hasattr(locals[func.__name__], 'dispatch'):
        orig_func = locals[func.__name__]

        def wrapper(*args, **kwargs):
            ret, ok = orig_func.dispatch(*args, **kwargs)
            if ok:
                return ret
            return func(*args, **kwargs)
        wrapper.isoverload = True
        wrapper.dispatch = make_dispatcher(func, orig_func.dispatch)
        wrapper.next = orig_func
        wrapper.__name__ = func.__name__
        if hasattr(func, '__isabstractmethod__'):
            # Note that we can't reliably check that abstractmethod is
            # used consistently across overload variants, so we let a
            # static checker do it.
            wrapper.__isabstractmethod__ = func.__isabstractmethod__
        return wrapper
    else:
        # Return the initial overload variant.
        func.isoverload = True
        func.dispatch = make_dispatcher(func)
        func.next = None
        return func


def is_erased_type(t):
    return t is Any or isinstance(t, typevar)


def make_dispatcher(func, previous=None):
    """Create argument dispatcher for an overloaded function.

    Also handle chaining of multiple overload variants.
    """
    (args, varargs, varkw, defaults,
     kwonlyargs, kwonlydefaults, annotations) = inspect.getfullargspec(func)

    argtypes = []
    for arg in args:
        ann = annotations.get(arg)
        if isinstance(ann, forwardref):
            ann = ann.name
        if is_erased_type(ann):
            ann = None
        elif isinstance(ann, str):
            # The annotation is a string => evaluate it lazily when the
            # overloaded function is first called.
            frame = sys._getframe(2)
            t = [None]
            ann_str = ann
            def check(x):
                if not t[0]:
                    # Evaluate string in the context of the overload caller.
                    t[0] = eval(ann_str, frame.f_globals, frame.f_locals)
                    if is_erased_type(t[0]):
                        # Anything goes.
                        t[0] = object
                if isinstance(t[0], type):
                    return isinstance(x, t[0])
                else:
                    return t[0](x)
            ann = check
        argtypes.append(ann)

    maxargs = len(argtypes)
    minargs = maxargs
    if defaults:
        minargs = len(argtypes) - len(defaults)

    def dispatch(*args, **kwargs):
        if previous:
            ret, ok = previous(*args, **kwargs)
            if ok:
                return ret, ok

        nargs = len(args)
        if nargs < minargs or nargs > maxargs:
            # Invalid argument count.
            return None, False

        for i in range(nargs):
            argtype = argtypes[i]
            if argtype:
                if isinstance(argtype, type):
                    if not isinstance(args[i], argtype):
                        break
                else:
                    if not argtype(args[i]):
                        break
        else:
            return func(*args, **kwargs), True
        return None, False
    return dispatch


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


T = typevar('T')
KT = typevar('KT')
VT = typevar('VT')


class SupportsInt(Protocol):
    @abstractmethod
    def __int__(self) -> int: pass


class SupportsFloat(Protocol):
    @abstractmethod
    def __float__(self) -> float: pass


class SupportsAbs(Protocol[T]):
    @abstractmethod
    def __abs__(self) -> T: pass


class SupportsRound(Protocol[T]):
    @abstractmethod
    def __round__(self, ndigits: int = 0) -> T: pass


class Reversible(Protocol[T]):
    @abstractmethod
    def __reversed__(self) -> 'Iterator[T]': pass


class Sized(Protocol):
    @abstractmethod
    def __len__(self) -> int: pass


class Container(Protocol[T]):
    @abstractmethod
    def __contains__(self, x) -> bool: pass


class Iterable(Protocol[T]):
    @abstractmethod
    def __iter__(self) -> 'Iterator[T]': pass


class Iterator(Iterable[T], Protocol[T]):
    @abstractmethod
    def __next__(self) -> T: pass


class Sequence(Sized, Iterable[T], Container[T], AbstractGeneric[T]):
    @abstractmethod
    @overload
    def __getitem__(self, i: int) -> T: pass

    @abstractmethod
    @overload
    def __getitem__(self, s: slice) -> 'Sequence[T]': pass

    @abstractmethod
    def __reversed__(self, s: slice) -> Iterator[T]: pass

    @abstractmethod
    def index(self, x) -> int: pass

    @abstractmethod
    def count(self, x) -> int: pass


for t in list, tuple, str, bytes, range:
    Sequence.register(t)


class AbstractSet(Sized, Iterable[T], AbstractGeneric[T]):
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


class Mapping(Sized, Iterable[KT], AbstractGeneric[KT, VT]):
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
    @overload
    @abstractmethod
    def get(self, k: KT) -> VT: pass
    @overload
    @abstractmethod
    def get(self, k: KT, default: VT) -> VT: pass
    @overload
    @abstractmethod
    def pop(self, k: KT) -> VT: pass
    @overload
    @abstractmethod
    def pop(self, k: KT, default: VT) -> VT: pass
    @abstractmethod
    def popitem(self) -> Tuple[KT, VT]: pass
    @overload
    @abstractmethod
    def setdefault(self, k: KT) -> VT: pass
    @overload
    @abstractmethod
    def setdefault(self, k: KT, default: VT) -> VT: pass

    @overload
    @abstractmethod
    def update(self, m: 'Mapping[KT, VT]') -> None: pass
    @overload
    @abstractmethod
    def update(self, m: Iterable[Tuple[KT, VT]]) -> None: pass

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


class IO(AbstractGeneric[AnyStr]):
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
    @overload
    @abstractmethod
    def write(self, s: bytes) -> int: pass
    @overload
    @abstractmethod
    def write(self, s: bytearray) -> int: pass

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
