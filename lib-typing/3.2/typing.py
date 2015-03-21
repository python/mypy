# TODO:
# __all__ (should not include T, KT, VT)
# Support Python 3.2
# Make re, io submodules?
# Other things from mypy's typing.py:
# - Reversible, SupportsInt, SupportsFloat, SupportsAbs, SupportsRound

# TODO nits:
# Get rid of asserts that are the caller's fault.
# Docstrings (e.g. ABCs).

import abc
from abc import abstractmethod, abstractproperty
import collections.abc
import functools
import inspect
import re
import sys
import types

# Simple constants defined in the PEP.
PY2 = sys.version_info[0] == 2
PY3 = sys.version_info[0] >= 3
WINDOWS = sys.platform == 'win32'
POSIX = not WINDOWS


class TypingMeta(type):
    """Metaclass for every type defined below.

    This overrides __new__() to require an extra keyword parameter
    '_root', which serves as a guard against naive subclassing of the
    typing classes.  Any legitimate class defined using a metaclass
    derived from TypingMeta (including internal subclasses created by
    e.g.  Union[X, Y]) must pass _root=True.

    This also defines a dummy constructor (all the work is done in
    __new__) and a nicer repr().
    """

    def __new__(cls, name, bases, namespace, *, _root=False):
        if not _root:
            raise TypeError("Cannot subclass %s" %
                            (', '.join(map(_type_repr, bases)) or '()'))
        return super().__new__(cls, name, bases, namespace)

    def __init__(self, *args, **kwds):
        pass

    def _eval_type(self, globalns, localns):
        """Override this in subclasses to interpret forward references.

        For example, Union['C'] is internally stored as
        Union[_ForwardRef('C')], which should evaluate to _Union[C],
        where C is an object found in globalns or localns (searching
        localns first, of course).
        """
        return self

    def _has_type_var(self):
        return False

    def __repr__(self):
        return '%s.%s' % (self.__module__, self.__qualname__)


class Final:
    """Mix-in class to prevent instantiation."""

    def __new__(self, *args, **kwds):
        raise TypeError("Cannot instantiate %r" % self.__class__)


class _ForwardRef(TypingMeta):
    """Wrapper to hold a forward reference."""

    def __new__(cls, arg):
        if not isinstance(arg, str):
            raise TypeError('ForwardRef must be a string -- got %r' % (arg,))
        try:
            code = compile(arg, '<string>', 'eval')
        except SyntaxError:
            raise SyntaxError('ForwardRef must be an expression -- got %r' %
                              (arg,))
        self = super().__new__(cls, arg, (), {}, _root=True)
        self.__forward_arg__ = arg
        self.__forward_code__ = code
        self.__forward_evaluated__ = False
        self.__forward_value__ = None
        return self

    def _eval_type(self, globalns, localns):
        if not isinstance(localns, dict):
            raise TypeError('ForwardRef localns must be a dict -- got %r' %
                            (localns,))
        if not isinstance(globalns, dict):
            raise TypeError('ForwardRef globalns must be a dict -- got %r' %
                            (globalns,))
        if not self.__forward_evaluated__:
            self.__forward_value__ = eval(self.__forward_code__,
                                          globalns, localns)
            self.__forward_evaluated__ = True
        return self.__forward_value__

    def __repr__(self):
        return '_ForwardRef(%r)' % (self.__forward_arg__,)


def _has_type_var(t):
    return t is not None and isinstance(t, TypingMeta) and t._has_type_var()


def _eval_type(t, globalns, localns):
    if isinstance(t, TypingMeta):
        return t._eval_type(globalns, localns)
    else:
        return t


def _type_check(arg, msg):
    """Check that the argument is a type, and return it.

    As a special case, accept None and return type(None) instead.
    The msg argument is a human-readable error message, e.g.

        "Union[arg, ...]: arg should be a type."

    We append the repr() of the actual value (truncated to 100 chars).
    """
    if arg is None:
        return type(None)
    if isinstance(arg, str):
        arg = _ForwardRef(arg)
    if not isinstance(arg, type):
        raise TypeError(msg + " Got %.100r." % (arg,))
    return arg


def _type_repr(obj):
    """Return the repr() of an object, special-casing types.

    If obj is a type, we return a shorter version than the default
    type.__repr__, based on the module and qualified name, which is
    typically enough to uniquely identify a type.  For everything
    else, we fall back on repr(obj).
    """
    if isinstance(obj, type) and not isinstance(obj, TypingMeta):
        if obj.__module__ == 'builtins':
            return obj.__qualname__
        else:
            return '%s.%s' % (obj.__module__, obj.__qualname__)
    else:
        return repr(obj)


class AnyMeta(TypingMeta):
    """Metaclass for Any."""

    def __new__(cls, name, bases, namespace, _root=False):
        self = super().__new__(cls, name, bases, namespace, _root=_root)
        return self

    def __instancecheck__(self, instance):
        return True

    def __subclasscheck__(self, cls):
        if not isinstance(cls, type):
            return super().__subclasscheck__(cls)  # To TypeError.
        return True


class Any(Final, metaclass=AnyMeta, _root=True):
    """Special type indicating an unconstrained type.

    - Any object is an instance of Any.
    - Any class is a subclass of Any.
    - As a special case, Any and object are subclasses of each other.
    """


class TypeVar(TypingMeta, metaclass=TypingMeta, _root=True):
    """Type variable.

    Usage::

      T1 = TypeVar('T1')  # Unconstrained
      T2 = TypeVar('T2', t1, t2, ...)  # Constrained to any of (t1, t2, ...)

    For an unconstrained type variable T, isinstance(x, T) is false
    for all x, and similar for issubclass(cls, T).  Example::

      T = TypeVar('T')
      assert not isinstance(42, T)
      assert not issubclass(int, T)

    For a constrained type variable T, isinstance(x, T) is true for
    any x that is an instance of at least one of T's constraints,
    and similar for issubclass(cls, T).  Example::

      AnyStr = TypeVar('AnyStr', str, bytes)
      # AnyStr behaves similar to Union[str, bytes] (but not exactly!)
      assert not isinstance(42, AnyStr)
      assert isinstance('', AnyStr)
      assert isinstance(b'', AnyStr)
      assert not issubclass(int, AnyStr)
      assert issubclass(str, AnyStr)
      assert issubclass(bytes, AnyStr)

    Type variables that are distinct objects are never equal (even if
    created with the same parameters).

    You can temporarily *bind* a type variable to a specific type by
    calling its bind() method and using the result as a context
    manager (i.e., in a with-statement).  Example::

      with T.bind(int):
          # In this block, T is nearly an alias for int.
          assert isinstance(42, T)
          assert issubclass(int, T)

    There is still a difference between T and int; issubclass(T, int)
    is False.  However, issubclass(int, T) is true.

    Binding a constrained type variable will replace the binding type
    with the most derived of its constraints that matches.  Example::

      class MyStr(str):
          pass

      with AnyStr.bind(MyStr):
          # In this block, AnyStr is an alias for str, not for MyStr.
          assert isinstance('', AnyStr)
          assert issubclass(str, AnyStr)
          assert not isinstance(b'', AnyStr)
          assert not issubclass(bytes, AnyStr)

    """

    def __new__(cls, name, *constraints):
        self = super().__new__(cls, name, (Final,), {}, _root=True)
        msg = "TypeVar(name, constraint, ...): constraints must be types."
        self.__constraints__ = tuple(_type_check(t, msg) for t in constraints)
        self.__binding__ = None
        return self

    def _has_type_var(self):
        return True

    def __repr__(self):
        return '~' + self.__name__

    def __instancecheck__(self, instance):
        if self.__binding__ is not None:
            return isinstance(instance, self.__binding__)
        elif not self.__constraints__:
            return False
        else:
            return isinstance(instance, Union[self.__constraints__])

    def __subclasscheck__(self, cls):
        if cls is self:
            return True
        elif self.__binding__ is not None:
            return issubclass(cls, self.__binding__)
        elif not self.__constraints__:
            return False
        else:
            return issubclass(cls, Union[self.__constraints__])

    def bind(self, binding):
        binding = _type_check(binding, "TypeVar.bind(t): t must be a type.")
        if self.__constraints__:
            best = None
            for t in self.__constraints__:
                if (issubclass(binding, t) and
                    (best is None or issubclass(t, best))):
                    best = t
            if best is None:
                raise TypeError(
                    "TypeVar.bind(t): t must match one of the constraints.")
            binding = best
        return VarBinding(self, binding)

    def _bind(self, binding):
        old_binding = self.__binding__
        self.__binding__ = binding
        return old_binding

    def _unbind(self, binding, old_binding):
        assert self.__binding__ is binding, (self.__binding__,
                                             binding, old_binding)
        self.__binding__ = old_binding


# Compatibility for for mypy's typevar().
def typevar(name, values=()):
    return TypeVar(name, *values)


class VarBinding:
    """TypeVariable binding returned by TypeVar.bind()."""

    # TODO: This is not thread-safe.  We could solve this in one of
    # two ways: by using a lock or by using thread-local state.  But
    # either of these feels overly heavy, and still doesn't work
    # e.g. in an asyncio Task.

    def __init__(self, var, binding):
        assert isinstance(var, TypeVar), (var, binding)
        assert isinstance(binding, type), (var, binding)
        self._var = var
        self._binding = binding
        self._old_binding = None
        self._entered = False

    def __enter__(self):
        if self._entered:
            # This checks for the following scenario:
            # bv = T.bind(<some_type>)
            # with bv:
            #     with bv:  # Will raise here.
            #         ...
            # However, the following scenario is OK (if somewhat odd):
            # bv = T.bind(<some_type>)
            # with bv:
            #     ...
            # with bv:
            #     ...
            # The following scenario is also fine:
            # with T.bind(<some_type>):
            #     with T.bind(<some_other_type>):
            #         ...
            raise TypeError("Cannot reuse variable binding recursively.")
        self._old_binding = self._var._bind(self._binding)
        self._entered = True

    def __exit__(self, *args):
        try:
            self._var._unbind(self._binding, self._old_binding)
        finally:
            self._entered = False
            self._old_binding = None


# Some unconstrained type variables.  These are used by the container types.
# TODO: Don't export these.
T = TypeVar('T')  # Any type.
KT = TypeVar('KT')  # Key type.
VT = TypeVar('VT')  # Value type.

# A useful type variable with constraints.  This represents string types.
# TODO: What about bytearray, memoryview?
AnyStr = TypeVar('AnyStr', bytes, str)


class UnionMeta(TypingMeta):
    """Metaclass for Union."""

    def __new__(cls, name, bases, namespace, parameters=None, _root=False):
        if parameters is None:
            return super().__new__(cls, name, bases, namespace, _root=_root)
        if not isinstance(parameters, tuple):
            raise TypeError("Expected parameters=<tuple>")
        # Flatten out Union[Union[...], ...] and type-check non-Union args.
        params = []
        msg = "Union[arg, ...]: each arg must be a type."
        for p in parameters:
            if isinstance(p, UnionMeta):
                params.extend(p.__union_params__)
            else:
                params.append(_type_check(p, msg))
        # Weed out strict duplicates, preserving the first of each occurrence.
        all_params = set(params)
        if len(all_params) < len(params):
            new_params = []
            for t in params:
                if t in all_params:
                    new_params.append(t)
                    all_params.remove(t)
            params = new_params
            assert not all_params, all_params
        # Weed out subclasses.
        # E.g. Union[int, Employee, Manager] == Union[int, Employee].
        # If Any or object is present it will be the sole survivor.
        # If both Any and object are present, Any wins.
        all_params = set(params)
        for t1 in params:
            if t1 is Any:
                return Any
            if any(issubclass(t1, t2) for t2 in all_params - {t1}):
                all_params.remove(t1)
        # It's not a union if there's only one type left.
        if len(all_params) == 1:
            return all_params.pop()
        # Create a new class with these params.
        self = super().__new__(cls, name, bases, {}, _root=True)
        self.__union_params__ = tuple(t for t in params if t in all_params)
        self.__union_set_params__ = frozenset(self.__union_params__)
        return self

    def _eval_type(self, globalns, localns):
        p = tuple(_eval_type(t, globalns, localns)
                  for t in self.__union_params__)
        if p == self.__union_params__:
            return self
        else:
            return self.__class__(self.__name__, self.__bases__, {},
                                  p, _root=True)

    def _has_type_var(self):
        if self.__union_params__:
            for t in self.__union_params__:
                if _has_type_var(t):
                    return True
        return False

    def __repr__(self):
        r = super().__repr__()
        if self.__union_params__:
            r += '[%s]' % (', '.join(_type_repr(t)
                                     for t in self.__union_params__))
        return r

    def __getitem__(self, parameters):
        if self.__union_params__ is not None:
            raise TypeError(
                "Cannot subscript an existing Union. Use Union[u, t] instead.")
        if parameters == ():
            raise TypeError("Cannot take a Union of no types.")
        if not isinstance(parameters, tuple):
            parameters = (parameters,)
        return self.__class__(self.__name__, self.__bases__,
                              dict(self.__dict__), parameters, _root=True)

    def __eq__(self, other):
        if not isinstance(other, UnionMeta):
            return NotImplemented
        return self.__union_set_params__ == other.__union_set_params__

    def __hash__(self):
        return hash(self.__union_set_params__)

    def __instancecheck__(self, instance):
        return any(isinstance(instance, t) for t in self.__union_params__)

    def __subclasscheck__(self, cls):
        if self.__union_params__ is None:
            return isinstance(cls, UnionMeta)
        elif isinstance(cls, UnionMeta):
            if cls.__union_params__ is None:
                return False
            return all(issubclass(c, self) for c in (cls.__union_params__))
        elif isinstance(cls, TypeVar):
            if cls in self.__union_params__:
                return True
            if cls.__constraints__:
                return issubclass(Union[cls.__constraints__], self)
            return False
        else:
            return any(issubclass(cls, t) for t in self.__union_params__)


class Union(Final, metaclass=UnionMeta, _root=True):
    """Union type; Union[X, Y] means either X or Y.

    To define a union, use e.g. Union[int, str].  Details:

    - The arguments must be types and there must be at least one.

    - None as an argument is a special case and is replaced by
      type(None).

    - Unions of unions are flattened, e.g.::

        Union[Union[int, str], float] == Union[int, str, float]

    - Unions of a single argument vanish, e.g.::

        Union[int] == int  # The constructore actually returns int

    - Redundant arguments are skipped, e.g.::

        Union[int, str, int] == Union[int, str]

    - When comparing unions, the argument order is ignored, e.g.::

        Union[int, str] == Union[str, int]

    - When two arguments have a subclass relationship, the least
      derived argument is kept, e.g.::

        class Employee: pass
        class Manager(Employee): pass
        Union[int, Employee, Manager] == Union[int, Employee]
        Union[Manager, int, Employee] == Union[int, Employee]
        Union[Employee, Manager] == Employee

    - Corollary: if Any is present it is the sole survivor, e.g.::

        Union[int, Any] == Any

    - Similar for object::

        Union[int, object] == object

    - To cut a tie: Union[object, Any] == Union[Any, object] == Any.

    - You cannot subclass or instantiate a union.

    - You cannot write Union[X][Y] (what would it mean?).

    - You can use Optional[X] as a shorthand for Union[X, None].
    """

    # Unsubscripted Union type has params set to None.
    __union_params__ = None
    __union_set_params__ = None


class OptionalMeta(TypingMeta):
    """Metaclass for Optional."""

    def __new__(cls, name, bases, namespace, _root=False):
        return super().__new__(cls, name, bases, namespace, _root=_root)

    def __getitem__(self, arg):
        arg = _type_check(arg, "Optional[t] requires a single type.")
        return Union[arg, type(None)]


class Optional(Final, metaclass=OptionalMeta, _root=True):
    """Optional type.

    Optional[X] is equivalent to Union[X, type(None)].
    """


class TupleMeta(TypingMeta):
    """Metaclass for Tuple."""

    def __new__(cls, name, bases, namespace, parameters=None, _root=False):
        self = super().__new__(cls, name, bases, namespace, _root=_root)
        self.__tuple_params__ = parameters
        return self

    def _has_type_var(self):
        if self.__tuple_params__:
            for t in self.__tuple_params__:
                if _has_type_var(t):
                    return True
        return False

    def _eval_type(self, globalns, localns):
        tp = self.__tuple_params__
        if tp is None:
            return self
        p = tuple(_eval_type(t, globalns, localns) for t in tp)
        if p == self.__tuple_params__:
            return self
        else:
            return self.__class__(self.__name__, self.__bases__, {},
                                  p, _root=True)

    def __repr__(self):
        r = super().__repr__()
        if self.__tuple_params__ is not None:
            r += '[%s]' % (
                ', '.join(_type_repr(p) for p in self.__tuple_params__))
        return r

    def __getitem__(self, parameters):
        if self.__tuple_params__ is not None:
            raise TypeError("Cannot re-parameterize %r" % (self,))
        if not isinstance(parameters, tuple):
            parameters = (parameters,)
        msg = "Class[arg, ...]: each arg must be a type."
        parameters = tuple(_type_check(p, msg) for p in parameters)
        return self.__class__(self.__name__, self.__bases__,
                              dict(self.__dict__), parameters, _root=True)

    def __eq__(self, other):
        if not isinstance(other, TupleMeta):
            return NotImplemented
        return self.__tuple_params__ == other.__tuple_params__

    def __hash__(self):
        return hash(self.__tuple_params__)

    def __instancecheck__(self, t):
        if not isinstance(t, tuple):
            return False
        if self.__tuple_params__ is None:
            return True
        return (len(t) == len(self.__tuple_params__) and
                all(isinstance(x, p)
                    for x, p in zip(t, self.__tuple_params__)))

    def __subclasscheck__(self, cls):
        if not isinstance(cls, type):
            return super().__subclasscheck__(cls)  # To TypeError.
        if issubclass(cls, tuple):
            return True  # Special case.
        if not isinstance(cls, TupleMeta):
            return super().__subclasscheck__(cls)  # False.
        if self.__tuple_params__ is None:
            return True
        if cls.__tuple_params__ is None:
            return False  # ???
        # Covariance.
        return (len(self.__tuple_params__) == len(cls.__tuple_params__) and
                all(issubclass(x, p)
                    for x, p in zip(cls.__tuple_params__,
                                    self.__tuple_params__)))


class Tuple(Final, metaclass=TupleMeta, _root=True):
    """Tuple type; Tuple[X, Y] is the cross-product type of X and Y.

    Example: Tuple[T1, T2] is a tuple of two elements corresponding
    to type variables T1 and T2.  Tuple[int, float, str] is a tuple
    of an int, a float and a string.

    To specify a variable-length tuple of homogeneous type, use Sequence[T].
    """


class CallableMeta(TypingMeta):
    """Metaclass for Callable."""

    def __new__(cls, name, bases, namespace, _root=False,
                args=None, result=None):
        if args is None and result is None:
            pass  # Must be 'class Callable'.
        else:
            if args is not Ellipsis:
                if not isinstance(args, list):
                    raise TypeError("Callable[args, result]: "
                                    "args must be a list."
                                    " Got %.100r." % (args,))
                msg = "Callable[[arg, ...], result]: each arg must be a type."
                args = tuple(_type_check(arg, msg) for arg in args)
            msg = "Callable[args, result]: result must be a type."
            result = _type_check(result, msg)
        self = super().__new__(cls, name, bases, namespace, _root=_root)
        self.__args__ = args
        self.__result__ = result
        return self

    def _has_type_var(self):
        if self.__args__:
            for t in self.__args__:
                if _has_type_var(t):
                    return True
        return _has_type_var(self.__result__)

    def _eval_type(self, globalns, localns):
        if self.__args__ is None and self.__result__ is None:
            return self
        args = [_eval_type(t, globalns, localns) for t in self.__args__]
        result = _eval_type(self.__result__, globalns, localns)
        if args == self.__args__ and result == self.__result__:
            return self
        else:
            return self.__class__(self.__name__, self.__bases__, {},
                                  args=args, result=result, _root=True)

    def __repr__(self):
        r = super().__repr__()
        if self.__args__ is not None or self.__result__ is not None:
            r += '%s[[%s], %s]' % (self.__qualname__,
                                   ', '.join(_type_repr(t)
                                             for t in self.__args__),
                                   _type_repr(self.__result__))
        return r

    def __getitem__(self, parameters):
        if self.__args__ is not None or self.__result__ is not None:
            raise TypeError("This Callable type is already parameterized.")
        if not isinstance(parameters, tuple) or len(parameters) != 2:
            raise TypeError(
                "Callable must be used as Callable[[arg, ...], result].")
        args, result = parameters
        return self.__class__(self.__name__, self.__bases__,
                              dict(self.__dict__), _root=True,
                              args=args, result=result)

    def __eq__(self, other):
        if not isinstance(other, CallableMeta):
            return NotImplemented
        return (self.__args__ == other.__args__ and
                self.__result__ == other.__result__)

    def __hash__(self):
        return hash(self.__args__) ^ hash(self.__result__)

    def __instancecheck__(self, instance):
        if not callable(instance):
            return False
        if self.__args__ is None and self.__result__ is None:
            return True
        assert self.__args__ is not None
        assert self.__result__ is not None
        my_args, my_result = self.__args__, self.__result__
        # Would it be better to use Signature objects?
        try:
            (args, varargs, varkw, defaults, kwonlyargs, kwonlydefaults,
             annotations) = inspect.getfullargspec(instance)
        except TypeError:
            return False  # We can't find the signature.  Give up.
        msg = ("When testing isinstance(<callable>, Callable[...], "
               "<calleble>'s annotations must be types.")
        if my_args is not Ellipsis:
            if kwonlyargs and (not kwonlydefaults or
                               len(kwonlydefaults) < len(kwonlyargs)):
                return False
            if isinstance(instance, types.MethodType):
                # For methods, getfullargspec() includes self/cls,
                # but it's not part of the call signature, so drop it.
                del args[0]
            min_call_args = len(args)
            if defaults:
                min_call_args -= len(defaults)
            if varargs:
                max_call_args = 999999999
                if len(args) < len(my_args):
                    args += [varargs] * (len(my_args) - len(args))
            else:
                max_call_args = len(args)
            if not min_call_args <= len(my_args) <= max_call_args:
                return False
            for my_arg_type, name in zip(my_args, args):
                if name in annotations:
                    annot_type = _type_check(annotations[name], msg)
                else:
                    annot_type = Any
                if not issubclass(my_arg_type, annot_type):
                    return False
                # TODO: If mutable type, check invariance?
        if 'return' in annotations:
            annot_return_type = _type_check(annotations['return'], msg)
            # Note contravariance here!
            if not issubclass(annot_return_type, my_result):
                return False
        # Can't find anything wrong...
        return True

    def __subclasscheck__(self, cls):
        # Compute issubclass(cls, self).
        if not isinstance(cls, CallableMeta):
            return super().__subclasscheck__(cls)
        if self.__args__ is None and self.__result__ is None:
            return True
        # We're not doing covariance or contravariance -- this is *invariance*.
        return self == cls


class Callable(Final, metaclass=CallableMeta, _root=True):
    """Callable type; Callable[[int], str] is a function of (int) -> str.

    The subscription syntax must always be used with exactly two
    values: the argument list and the return type.  The argument list
    must be a list of types; the return type must be a single type.

    There is no syntax to indicate optional or keyword arguments,
    such function types are rarely used as callback types.
    """


class GenericMeta(TypingMeta, abc.ABCMeta):
    """Metaclass for generic types."""

    # TODO: Constrain more how Generic is used; only a few
    # standard patterns should be allowed.

    __extra__ = None

    def __new__(cls, name, bases, namespace, parameters=None, extra=None):
        if parameters is None:
            # Extract parameters from direct base classes.  Only
            # direct bases are considered and only those that are
            # themselves generic, and parameterized with type
            # variables.  Don't use bases like Any, Union, Tuple,
            # Callable or type variables.
            params = None
            for base in bases:
                if isinstance(base, TypingMeta):
                    if not isinstance(base, GenericMeta):
                        raise TypeError(
                            "You cannot inherit from magic class %s" %
                            repr(base))
                    if base.__parameters__ is None:
                        continue  # The base is unparameterized.
                    for bp in base.__parameters__:
                        if _has_type_var(bp) and not isinstance(bp, TypeVar):
                            raise TypeError(
                                "Cannot inherit from a generic class "
                                "parameterized with "
                                "non-type-variable %s" % bp)
                        if params is None:
                            params = []
                        if bp not in params:
                            params.append(bp)
            if params is not None:
                parameters = tuple(params)
        self = super().__new__(cls, name, bases, namespace, _root=True)
        self.__parameters__ = parameters
        if extra is not None:
            self.__extra__ = extra
        # Else __extra__ is inherited, eventually from the
        # (meta-)class default above.
        return self

    def _has_type_var(self):
        if self.__parameters__:
            for t in self.__parameters__:
                if _has_type_var(t):
                    return True
        return False

    def __repr__(self):
        r = super().__repr__()
        if self.__parameters__ is not None:
            r += '[%s]' % (
                ', '.join(_type_repr(p) for p in self.__parameters__))
        return r

    def __eq__(self, other):
        if not isinstance(other, GenericMeta):
            return NotImplemented
        return (self.__name__ == other.__name__ and
                self.__parameters__ == other.__parameters__)

    def __hash__(self):
        return hash((self.__name__, self.__parameters__))

    def __getitem__(self, params):
        if not isinstance(params, tuple):
            params = (params,)
        if not params:
            raise TypeError("Cannot have empty parameter list")
        msg = "Parameters to generic types must be types."
        params = tuple(_type_check(p, msg) for p in params)
        if self.__parameters__ is None:
            for p in params:
                if not isinstance(p, TypeVar):
                    raise TypeError("Initial parameters must be "
                                    "type variables; got %s" % p)
        else:
            if len(params) != len(self.__parameters__):
                raise TypeError("Cannot change parameter count from %d to %d" %
                                (len(self.__parameters__), len(params)))
            for new, old in zip(params, self.__parameters__):
                if isinstance(old, TypeVar) and not old.__constraints__:
                    # Substituting for an unconstrained TypeVar is always OK.
                    continue
                if not issubclass(new, old):
                    raise TypeError(
                        "Cannot substitute %s for %s in %s" %
                        (_type_repr(new), _type_repr(old), self))

        return self.__class__(self.__name__, self.__bases__,
                              dict(self.__dict__),
                              parameters=params, extra=self.__extra__)

    def __subclasscheck__(self, cls):
        if super().__subclasscheck__(cls):
            return True
        if self.__extra__ is None:
            return False
        return issubclass(cls, self.__extra__)

    def __instancecheck__(self, obj):
        if super().__instancecheck__(obj):
            return True
        if self.__extra__ is None:
            return False
        return isinstance(obj, self.__extra__)


class Generic(metaclass=GenericMeta):
    """Abstract base class for generic types.

    A generic type is typically declared by inheriting from an
    instantiation of this class with one or more type variables.
    For example, a generic mapping type might be defined as::

      class Mapping(Generic[KT, VT]):
          def __getitem__(self, key: KT) -> VT:
              ...
          # Etc.

    This class can then be used as follows::

      def lookup_name(mapping: Mapping, key: KT, default: VT) -> VT:
          try:
              return mapping[key]
          except KeyError:
              return default

    For clarity the type variables may be redefined, e.g.::

      X = TypeVar('X')
      Y = TypeVar('Y')
      def lookup_name(mapping: Mapping[X, Y], key: X, default: Y) -> Y:
          # Same body as above.
    """


class Undefined:
    """An undefined value.

    Example::

      x = Undefined(typ)

    This tells the type checker that x has the given type but its
    value should be considered undefined.  At runtime x is an instance
    of Undefined.  The actual type can be introspected by looking at
    x.__type__ and its str() and repr() are defined, but any other
    operations or attributes will raise an exception.

    An alternative syntax is also supported:

      x = Undefined  # type: typ

    This has the same meaning to the static type checker but uses less
    overhead at run-time, at the cost of not being introspectible.

    NOTE: Do not under any circumstances check for Undefined.  We
    don't want this to become something developers rely upon, like
    JavaScript's undefined.  Code that returns or uses an Undefined
    value in any way should be considered broken.  Static type
    checkers should warn about using potentially Undefined values.
    """

    __slots__ = ['__type__']

    def __new__(cls, typ):
        typ = _type_check(typ, "Undefined(t): t must be a type.")
        self = super().__new__(cls)
        self.__type__ = typ
        return self

    __hash__ = None

    def __repr__(self):
        return '%s(%s)' % (_type_repr(self.__class__),
                           _type_repr(self.__type__))


def cast(typ, val):
    """Cast a value to a type.

    This returns the value unchanged.  To the type checker this
    signals that the return value has the designated type, but at
    runtime we intentionally don't check anything (we want this
    to be as fast as possible).
    """
    return val


def get_type_hints(obj, globalns=None, localns=None):
    """Return type hints for a function or method object.

    This is often the same as obj.__annotations__, but it handles
    forward references encoded as string literals, and if necessary
    adds Optional[t] if a default value equal to None is set.

    BEWARE -- the behavior of globalns and localns is counterintuitive
    (unless you are familiar with how eval() and exec() work).  The
    search order is locals first, then globals.

    - If no dict arguments are passed, the defaults are taken from the
      globals and locals of the caller, respectively.

    - If one dict argument is passed, it is used for both globals and
      locals.

    - If two dict arguments are passed, they specify globals and
      locals, respectively.
    """
    if getattr(obj, '__no_type_check__', None):
        return {}
    if globalns is None:
        globalns = sys._getframe(1).f_globals
        if localns is None:
            localns = sys._getframe(1).f_locals
    elif localns is None:
        localns = globalns
    sig = inspect.Signature.from_function(obj)
    hints = dict(obj.__annotations__)
    for name, value in hints.items():
        if isinstance(value, str):
            value = _ForwardRef(value)
        value = _eval_type(value, globalns, localns)
        if name in sig.parameters and sig.parameters[name].default is None:
            value = Optional[value]
        hints[name] = value
    return hints


# TODO: Also support this as a class decorator.
def no_type_check(func):
    """Decorator to indicate that annotations are not type hints.

    This mutates the function in place.
    """
    func.__no_type_check__ = True
    return func


def no_type_check_decorator(decorator):
    """Decorator to give another decorator the @no_type_check effect.

    This wraps the decorator with something that wraps the decorated
    function in @no_type_check.
    """

    @functools.wraps(decorator)
    def wrapped_decorator(*args, **kwds):
        func = decorator(*args, **kwds)
        func = no_type_check(func)
        return func

    return wrapped_decorator


def overload(func):
    raise RuntimeError("Overloading is only supported in library stubs")


# Various ABCs mimicking those in collections.abc.
# A few are simply re-exported for completeness.

Hashable = collections.abc.Hashable  # Not generic.


class Iterable(Generic[T], extra=collections.abc.Iterable):
    pass


class Iterator(Iterable, extra=collections.abc.Iterator):
    pass


Sized = collections.abc.Sized  # Not generic.


class Container(Generic[T], extra=collections.abc.Container):
    pass


# Callable was defined earlier.


class AbstractSet(Sized, Iterable, Container, extra=collections.abc.Set):
    pass


class MutableSet(AbstractSet, extra=collections.abc.MutableSet):
    pass


class Mapping(Sized, Iterable[KT], Container[KT], Generic[KT, VT],
              extra=collections.abc.Mapping):
    pass


class MutableMapping(Mapping, extra=collections.abc.MutableMapping):
    pass


class Sequence(Sized, Iterable, Container, extra=collections.abc.Sequence):
    pass


class MutableSequence(Sequence, extra=collections.abc.MutableSequence):
    pass


class ByteString(Sequence[int], extra=collections.abc.ByteString):
    pass


ByteString.register(type(memoryview(b'')))


class _ListMeta(GenericMeta):

    def __instancecheck__(self, obj):
        if not super().__instancecheck__(obj):
            return False
        itemtype = self.__parameters__[0]
        for x in obj:
            if not isinstance(x, itemtype):
                return False
        return True


class List(list, MutableSequence, metaclass=_ListMeta):
    pass


class _SetMeta(GenericMeta):

    def __instancecheck__(self, obj):
        if not super().__instancecheck__(obj):
            return False
        itemtype = self.__parameters__[0]
        for x in obj:
            if not isinstance(x, itemtype):
                return False
        return True


class Set(set, MutableSet, metaclass=_SetMeta):
    pass


class MappingView(Sized, Iterable, extra=collections.abc.MappingView):
    pass


class KeysView(MappingView, Set[KT], extra=collections.abc.KeysView):
    pass


# TODO: Enable Set[Tuple[KT, VT]] instead of Generic[KT, VT].
class ItemsView(MappingView, Generic[KT, VT], extra=collections.abc.ItemsView):
    pass


class ValuesView(MappingView, extra=collections.abc.ValuesView):
    pass


class _DictMeta(GenericMeta):

    def __instancecheck__(self, obj):
        if not super().__instancecheck__(obj):
            return False
        keytype, valuetype = self.__parameters__
        for key, value in obj.items():
            if not (isinstance(key, keytype) and
                    isinstance(value, valuetype)):
                return False
        return True


class Dict(dict, MutableMapping, metaclass=_DictMeta):
    pass


def NamedTuple(typename, fields):
    """Typed version of namedtuple.

    Usage::

        Employee = typing.NamedTuple('Employee', [('name', str), 'id', int)])

    This is equivalent to::

        Employee = collections.namedtuple('Employee', ['name', 'id'])

    The resulting class has one extra attribute: _field_types,
    giving a dict mapping field names to types.  (The field names
    are in the _fields attribute, which is part of the namedtuple
    API.)
    """
    fields = [(n, t) for n, t in fields]
    cls = collections.namedtuple(typename, [n for n, t in fields])
    cls._field_types = dict(fields)
    return cls


class IO(Generic[AnyStr]):
    """Generic base class for TextIO and BinaryIO.

    This is an abstract, generic version of the return of open().

    NOTE: This does not distinguish between the different possible
    classes (text vs. binary, read vs. write vs. read/write,
    append-only, unbuffered).  The TextIO and BinaryIO subclasses
    below capture the distinctions between text vs. binary, which is
    pervasive in the interface; however we currently do not offer a
    way to track the other distinctions in the type system.
    """

    @abstractproperty
    def mode(self) -> str:
        pass

    @abstractproperty
    def name(self) -> str:
        pass

    @abstractmethod
    def close(self) -> None:
        pass

    @abstractmethod
    def closed(self) -> bool:
        pass

    @abstractmethod
    def fileno(self) -> int:
        pass

    @abstractmethod
    def flush(self) -> None:
        pass

    @abstractmethod
    def isatty(self) -> bool:
        pass

    @abstractmethod
    def read(self, n: int = -1) -> AnyStr:
        pass

    @abstractmethod
    def readable(self) -> bool:
        pass

    @abstractmethod
    def readline(self, limit: int = -1) -> AnyStr:
        pass

    @abstractmethod
    def readlines(self, hint: int = -1) -> List[AnyStr]:
        pass

    @abstractmethod
    def seek(self, offset: int, whence: int = 0) -> int:
        pass

    @abstractmethod
    def seekable(self) -> bool:
        pass

    @abstractmethod
    def tell(self) -> int:
        pass

    @abstractmethod
    def truncate(self, size: int = None) -> int:
        pass

    @abstractmethod
    def writable(self) -> bool:
        pass

    @abstractmethod
    def write(self, s: AnyStr) -> int:
        pass

    @abstractmethod
    def writelines(self, lines: List[AnyStr]) -> None:
        pass

    @abstractmethod
    def __enter__(self) -> 'IO[AnyStr]':
        pass

    @abstractmethod
    def __exit__(self, type, value, traceback) -> None:
        pass


class BinaryIO(IO[bytes]):
    """Typed version of the return of open() in binary mode."""

    @abstractmethod
    def write(self, s: Union[bytes, bytearray]) -> int:
        pass

    @abstractmethod
    def __enter__(self) -> 'BinaryIO':
        pass


class TextIO(IO[str]):
    """Typed version of the return of open() in text mode."""

    @abstractproperty
    def buffer(self) -> BinaryIO:
        pass

    @abstractproperty
    def encoding(self) -> str:
        pass

    @abstractproperty
    def errors(self) -> str:
        pass

    @abstractproperty
    def line_buffering(self) -> bool:
        pass

    @abstractproperty
    def newlines(self) -> Any:
        pass

    @abstractmethod
    def __enter__(self) -> 'TextIO':
        pass


class _TypeAlias:
    """Internal helper class for defining generic variants of concrete types.

    Note that this is not a type; let's call it a pseudo-type.  It can
    be used in instance and subclass checks, e.g. isinstance(m, Match)
    or issubclass(type(m), Match).  However, it cannot be itself the
    target of an issubclass() call; e.g. issubclass(Match, C) (for
    some arbitrary class C) raises TypeError rather than returning
    False.
    """

    def __init__(self, name, type_var, impl_type, type_checker):
        """Constructor.

        Args:
            name: The name, e.g. 'Pattern'.
            type_var: The type parameter, e.g. AnyStr, or the
                specific type, e.g. str.
            impl_type: The implementation type.
            type_checker: Function that takes an impl_type instance.
                and returns a value that should be a type_var instance.
        """
        assert isinstance(name, str), repr(name)
        assert isinstance(type_var, type), repr(type_var)
        assert isinstance(impl_type, type), repr(impl_type)
        assert not isinstance(impl_type, TypingMeta), repr(impl_type)
        self.name = name  # The name, e.g. 'Pattern'
        self.type_var = type_var  # The type parameter, e.g. 'AnyStr', or the specific type, e.g. 'str'
        self.impl_type = impl_type  # The implementation type
        self.type_checker = type_checker  # Function that takes an impl_type instance and returns a value that should be a type_var instance

    def __repr__(self):
        return "%s[%s]" % (self.name, _type_repr(self.type_var))

    def __getitem__(self, parameter):
        assert isinstance(parameter, type), repr(parameter)
        if not isinstance(self.type_var, TypeVar):
            raise TypeError("%s cannot be further parameterized." % self)
        if not issubclass(parameter, self.type_var):
            raise TypeError("%s is not a valid substitution for %s." % (parameter, self.type_var))
        return self.__class__(self.name, parameter, self.impl_type, self.type_checker)

    def __instancecheck__(self, obj):
        return isinstance(obj, self.impl_type) and isinstance(self.type_checker(obj), self.type_var)

    def __subclasscheck__(self, cls):
        if isinstance(cls, _TypeAlias):
            # Covariance.  For now, we compare by name.
            return (cls.name == self.name and issubclass(cls.type_var, self.type_var))
        else:
            # Note that this is too lenient, because the
            # implementation type doesn't carry information about
            # whether it is about bytes or str (for example).
            return issubclass(cls, self.impl_type)


Pattern = _TypeAlias('Pattern', AnyStr, type(re.compile('')), lambda p: p.pattern)
Match =  _TypeAlias('Match', AnyStr, type(re.match('', '')), lambda m: m.re.pattern)
