from collections import namedtuple
import re
import sys
from unittest import TestCase, main
try:
    from unittest import mock
except ImportError:
    import mock  # 3rd party install, for PY3.2.

from typing import Any
from typing import TypeVar, T, KT, VT, AnyStr
from typing import Union, Optional
from typing import Tuple
from typing import Callable
from typing import Generic
from typing import Undefined
from typing import cast
from typing import get_type_hints
from typing import no_type_check, no_type_check_decorator
from typing import NamedTuple
from typing import IO, TextIO, BinaryIO
from typing import Pattern, Match
import typing


class ConstantsTests(TestCase):

    def test_py23(self):
        assert isinstance(typing.PY2, bool)
        assert isinstance(typing.PY3, bool)
        assert typing.PY3 == (not typing.PY2)

    def test_poswin(self):
        assert isinstance(typing.POSIX, bool)
        assert isinstance(typing.WINDOWS, bool)
        assert typing.POSIX == (not typing.WINDOWS)


class Employee:
    pass


class Manager(Employee):
    pass


class Founder(Employee):
    pass


class ManagingFounder(Manager, Founder):
    pass


class AnyTests(TestCase):

    def test_any_instance(self):
        self.assertIsInstance(Employee(), Any)
        self.assertIsInstance(42, Any)
        self.assertIsInstance(None, Any)
        self.assertIsInstance(object(), Any)

    def test_any_subclass(self):
        self.assertTrue(issubclass(Employee, Any))
        self.assertTrue(issubclass(int, Any))
        self.assertTrue(issubclass(type(None), Any))
        self.assertTrue(issubclass(object, Any))

    def test_others_any(self):
        self.assertFalse(issubclass(Any, Employee))
        self.assertFalse(issubclass(Any, int))
        self.assertFalse(issubclass(Any, type(None)))
        # However, Any is a subclass of object (this can't be helped).
        self.assertTrue(issubclass(Any, object))

    def test_repr(self):
        self.assertEqual(repr(Any), 'typing.Any')

    def test_errors(self):
        with self.assertRaises(TypeError):
            issubclass(42, Any)
        with self.assertRaises(TypeError):
            Any[int]  # Any is not a generic type.

    def test_cannot_subclass(self):
        with self.assertRaises(TypeError):
            class A(Any):
                pass

    def test_cannot_instantiate(self):
        with self.assertRaises(TypeError):
            Any()

    def test_cannot_subscript(self):
        with self.assertRaises(TypeError):
            Any[int]

    def test_any_is_subclass(self):
        # Any should be considered a subclass of everything.
        assert issubclass(Any, Any)
        assert issubclass(Any, typing.List)
        assert issubclass(Any, typing.List[int])
        assert issubclass(Any, typing.List[T])
        assert issubclass(Any, typing.Mapping)
        assert issubclass(Any, typing.Mapping[str, int])
        assert issubclass(Any, typing.Mapping[KT, VT])
        assert issubclass(Any, Generic)
        assert issubclass(Any, Generic[T])
        assert issubclass(Any, Generic[KT, VT])
        assert issubclass(Any, AnyStr)
        assert issubclass(Any, Union)
        assert issubclass(Any, Union[int, str])
        assert issubclass(Any, typing.Match)
        assert issubclass(Any, typing.Match[str])
        # These expressions must simply not fail.
        typing.Match[Any]
        typing.Pattern[Any]
        typing.IO[Any]


class TypeVarTests(TestCase):

    def test_isinstance(self):
        self.assertNotIsInstance(42, T)
        self.assertIsInstance(b'b', AnyStr)
        self.assertIsInstance('s', AnyStr)
        self.assertNotIsInstance(42, AnyStr)

    def test_issubclass(self):
        self.assertTrue(issubclass(T, Any))
        self.assertFalse(issubclass(int, T))
        self.assertTrue(issubclass(bytes, AnyStr))
        self.assertTrue(issubclass(str, AnyStr))
        self.assertTrue(issubclass(T, T))
        self.assertTrue(issubclass(AnyStr, AnyStr))

    def test_repr(self):
        self.assertEqual(repr(T), '~T')
        self.assertEqual(repr(KT), '~KT')
        self.assertEqual(repr(VT), '~VT')
        self.assertEqual(repr(AnyStr), '~AnyStr')

    def test_no_redefinition(self):
        self.assertNotEqual(TypeVar('T'), TypeVar('T'))
        self.assertNotEqual(TypeVar('T', int, str), TypeVar('T', int, str))

    def test_subclass_as_unions(self):
        self.assertTrue(issubclass(TypeVar('T', int, str),
                                   TypeVar('T', int, str)))
        self.assertTrue(issubclass(TypeVar('T', int), TypeVar('T', int, str)))
        self.assertTrue(issubclass(TypeVar('T', int, str),
                                   TypeVar('T', str, int)))
        A = TypeVar('A', int, str)
        B = TypeVar('B', int, str, float)
        self.assertTrue(issubclass(A, B))
        self.assertFalse(issubclass(B, A))

    def test_cannot_subclass_vars(self):
        with self.assertRaises(TypeError):
            class V(TypeVar('T')):
                pass

    def test_cannot_subclass_var_itself(self):
        with self.assertRaises(TypeError):
            class V(TypeVar):
                pass

    def test_cannot_instantiate_vars(self):
        with self.assertRaises(TypeError):
            TypeVar('A')()

    def test_bind(self):
        self.assertNotIsInstance(42, T)  # Baseline.
        with T.bind(int):
            self.assertIsInstance(42, T)
            self.assertNotIsInstance(3.14, T)
            self.assertTrue(issubclass(int, T))
            self.assertFalse(issubclass(T, int))
            self.assertFalse(issubclass(float, T))
        self.assertNotIsInstance(42, T)  # Baseline restored.

    def test_bind_reuse(self):
        self.assertNotIsInstance(42, T)  # Baseline.
        bv = T.bind(int)
        with bv:
            self.assertIsInstance(42, T)  # Bound.
            self.assertNotIsInstance(3.14, T)
        self.assertNotIsInstance(42, T)  # Baseline restored.
        # Reusing bv will work.
        with bv:
            self.assertIsInstance(42, T)  # Bound.
            self.assertNotIsInstance(3.14, T)
            # Reusing bv recursively won't work.
            with self.assertRaises(TypeError):
                with bv:
                    self.assertFalse("Should not get here")
            # Rebinding T explicitly will work.
            with T.bind(float):
                self.assertIsInstance(3.14, T)
                self.assertNotIsInstance(42, T)
            # Now the previous binding should be restored.
            self.assertIsInstance(42, T)
            self.assertNotIsInstance(3.14, T)
        self.assertNotIsInstance(42, T)  # Baseline restored.

    def test_bind_fail(self):
        # This essentially tests what happens when __enter__() raises
        # an exception.  __exit__() won't be called, but the
        # VarBinding and the TypeVar are still in consistent states.
        bv = T.bind(int)
        with mock.patch('typing.TypeVar._bind', side_effect=RuntimeError):
            with self.assertRaises(RuntimeError):
                with bv:
                    self.assertFalse("Should not get here")
        self.assertNotIsInstance(42, T)
        with bv:
            self.assertIsInstance(42, T)
        self.assertNotIsInstance(42, T)


class UnionTests(TestCase):

    def test_basics(self):
        u = Union[int, float]
        self.assertNotEqual(u, Union)
        self.assertIsInstance(42, u)
        self.assertIsInstance(3.14, u)
        self.assertTrue(issubclass(int, u))
        self.assertTrue(issubclass(float, u))

    def test_union_any(self):
        u = Union[Any]
        self.assertEqual(u, Any)
        u = Union[int, Any]
        self.assertEqual(u, Any)
        u = Union[Any, int]
        self.assertEqual(u, Any)

    def test_union_object(self):
        u = Union[object]
        self.assertEqual(u, object)
        u = Union[int, object]
        self.assertEqual(u, object)
        u = Union[object, int]
        self.assertEqual(u, object)

    def test_union_any_object(self):
        u = Union[object, Any]
        self.assertEqual(u, Any)
        u = Union[Any, object]
        self.assertEqual(u, Any)

    def test_unordered(self):
        u1 = Union[int, float]
        u2 = Union[float, int]
        self.assertEqual(u1, u2)

    def test_subclass(self):
        u = Union[int, Employee]
        self.assertIsInstance(Manager(), u)
        self.assertTrue(issubclass(Manager, u))

    def test_self_subclass(self):
        self.assertTrue(issubclass(Union[KT, VT], Union))
        self.assertFalse(issubclass(Union, Union[KT, VT]))

    def test_multiple_inheritance(self):
        u = Union[int, Employee]
        self.assertIsInstance(ManagingFounder(), u)
        self.assertTrue(issubclass(ManagingFounder, u))

    def test_single_class_disappears(self):
        t = Union[Employee]
        self.assertIs(t, Employee)

    def test_base_class_disappears(self):
        u = Union[Employee, Manager, int]
        self.assertEqual(u, Union[int, Employee])
        u = Union[Manager, int, Employee]
        self.assertEqual(u, Union[int, Employee])
        u = Union[Employee, Manager]
        self.assertIs(u, Employee)

    def test_weird_subclasses(self):
        u = Union[Employee, int, float]
        v = Union[int, float]
        self.assertTrue(issubclass(v, u))
        w = Union[int, Manager]
        self.assertTrue(issubclass(w, u))

    def test_union_union(self):
        u = Union[int, float]
        v = Union[u, Employee]
        self.assertEqual(v, Union[int, float, Employee])

    def test_repr(self):
        self.assertEqual(repr(Union), 'typing.Union')
        u = Union[Employee, int]
        self.assertEqual(repr(u), 'typing.Union[%s.Employee, int]' % __name__)
        u = Union[int, Employee]
        self.assertEqual(repr(u), 'typing.Union[int, %s.Employee]' % __name__)

    def test_cannot_subclass(self):
        with self.assertRaises(TypeError):
            class C(Union):
                pass
        with self.assertRaises(TypeError):
            class C(Union[int, str]):
                pass

    def test_cannot_instantiate(self):
        with self.assertRaises(TypeError):
            Union()
        u = Union[int, float]
        with self.assertRaises(TypeError):
            u()

    def test_optional(self):
        o = Optional[int]
        u = Union[int, None]
        self.assertEqual(o, u)
        self.assertIsInstance(42, o)
        self.assertIsInstance(None, o)
        self.assertNotIsInstance(3.14, o)

    def test_empty(self):
        with self.assertRaises(TypeError):
            Union[()]


class TypeVarUnionTests(TestCase):

    def test_simpler(self):
        A = TypeVar('A', int, str, float)
        B = TypeVar('B', int, str)
        assert issubclass(A, A)
        assert issubclass(B, B)
        assert issubclass(B, A)
        assert issubclass(A, Union[int, str, float])
        assert issubclass(Union[int, str, float], A)
        assert issubclass(Union[int, str], B)
        assert issubclass(B, Union[int, str])
        assert not issubclass(A, B)
        assert not issubclass(Union[int, str, float], B)
        assert not issubclass(A, Union[int, str])

    def test_var_union_subclass(self):
        self.assertTrue(issubclass(T, Union[int, T]))
        self.assertTrue(issubclass(KT, Union[KT, VT]))

    def test_var_union(self):
        TU = TypeVar('TU', Union[int, float])
        self.assertIsInstance(42, TU)
        self.assertIsInstance(3.14, TU)
        self.assertNotIsInstance('', TU)
        with TU.bind(int):
            # The effective binding is the union.
            self.assertIsInstance(42, TU)
            self.assertIsInstance(3.14, TU)
            self.assertNotIsInstance('', TU)
        with self.assertRaises(TypeError):
            with TU.bind(str):
                self.assertFalse("Should not get here")

    def test_var_union_and_more_precise(self):
        TU = TypeVar('TU', Union[int, float], int)
        with TU.bind(int):
            # The binding is ambiguous, but the second alternative
            # is strictly more precise.  Choose the more precise match.
            # The effective binding is int.
            self.assertIsInstance(42, TU)
            self.assertNotIsInstance(3.14, TU)
            self.assertNotIsInstance('', TU)
        with TU.bind(float):
            # The effective binding is the union.
            self.assertIsInstance(42, TU)
            self.assertIsInstance(3.14, TU)
            self.assertNotIsInstance('', TU)

    def test_var_union_overlapping(self):
        TU = TypeVar('TU', Union[int, float], Union[float, str])
        with TU.bind(int):
            # The effective binding is the first union.
            self.assertIsInstance(42, TU)
            self.assertIsInstance(3.14, TU)
            self.assertNotIsInstance('', TU)
        with TU.bind(float):
            # The binding is ambiguous, but neither constraint is a
            # subclass of the other.  Choose the first match.
            # The effective binding is the first union.
            self.assertIsInstance(42, TU)
            self.assertIsInstance(3.14, TU)
            self.assertNotIsInstance('', TU)
        with TU.bind(str):
            # The effective binding is the second union.
            self.assertNotIsInstance(42, TU)
            self.assertIsInstance(3.14, TU)
            self.assertIsInstance('', TU)


class TupleTests(TestCase):

    def test_basics(self):
        self.assertIsInstance((42, 3.14, ''), Tuple)
        self.assertIsInstance((42, 3.14, ''), Tuple[int, float, str])
        self.assertIsInstance((42,), Tuple[int])
        self.assertNotIsInstance((3.14,), Tuple[int])
        self.assertNotIsInstance((42, 3.14), Tuple[int, float, str])
        self.assertNotIsInstance((42, 3.14, 100), Tuple[int, float, str])
        self.assertNotIsInstance((42, 3.14, 100), Tuple[int, float])
        self.assertTrue(issubclass(Tuple[int, str], Tuple))
        self.assertTrue(issubclass(Tuple[int, str], Tuple[int, str]))
        self.assertFalse(issubclass(int, Tuple))
        self.assertFalse(issubclass(Tuple[float, str], Tuple[int, str]))
        self.assertFalse(issubclass(Tuple[int, str, int], Tuple[int, str]))
        self.assertFalse(issubclass(Tuple[int, str], Tuple[int, str, int]))
        self.assertTrue(issubclass(tuple, Tuple))
        self.assertFalse(issubclass(Tuple, tuple))  # Can't have it both ways.

    def test_tuple_subclass(self):
        class MyTuple(tuple):
            pass
        self.assertTrue(issubclass(MyTuple, Tuple))

    def test_repr(self):
        self.assertEqual(repr(Tuple), 'typing.Tuple')
        self.assertEqual(repr(Tuple[()]), 'typing.Tuple[]')
        self.assertEqual(repr(Tuple[int, float]), 'typing.Tuple[int, float]')

    def test_errors(self):
        with self.assertRaises(TypeError):
            issubclass(42, Tuple)
        with self.assertRaises(TypeError):
            issubclass(42, Tuple[int])


class CallableTests(TestCase):

    def test_basics(self):
        c = Callable[[int, float], str]

        def flub(a: int, b: float) -> str:
            return str(a * b)

        def flob(a: int, b: int) -> str:
            return str(a * b)

        self.assertIsInstance(flub, c)
        self.assertNotIsInstance(flob, c)

    def test_self_subclass(self):
        self.assertTrue(issubclass(Callable[[int], int], Callable))
        self.assertFalse(issubclass(Callable, Callable[[int], int]))
        self.assertTrue(issubclass(Callable[[int], int], Callable[[int], int]))
        self.assertFalse(issubclass(Callable[[Employee], int],
                                    Callable[[Manager], int]))
        self.assertFalse(issubclass(Callable[[Manager], int],
                                    Callable[[Employee], int]))
        self.assertFalse(issubclass(Callable[[int], Employee],
                                    Callable[[int], Manager]))
        self.assertFalse(issubclass(Callable[[int], Manager],
                                    Callable[[int], Employee]))

    def test_eq_hash(self):
        self.assertEqual(Callable[[int], int], Callable[[int], int])
        self.assertEqual(len({Callable[[int], int], Callable[[int], int]}), 1)
        self.assertNotEqual(Callable[[int], int], Callable[[int], str])
        self.assertNotEqual(Callable[[int], int], Callable[[str], int])
        self.assertNotEqual(Callable[[int], int], Callable[[int, int], int])
        self.assertNotEqual(Callable[[int], int], Callable[[], int])
        self.assertNotEqual(Callable[[int], int], Callable)

    def test_with_none(self):
        c = Callable[[None], None]

        def flub(self: None) -> None:
            pass

        def flab(self: Any) -> None:
            pass

        def flob(self: None) -> Any:
            pass

        self.assertIsInstance(flub, c)
        self.assertIsInstance(flab, c)
        self.assertNotIsInstance(flob, c)  # Test contravariance.

    def test_with_subclasses(self):
        c = Callable[[Employee, Manager], Employee]

        def flub(a: Employee, b: Employee) -> Manager:
            return Manager()

        def flob(a: Manager, b: Manager) -> Employee:
            return Employee()

        self.assertIsInstance(flub, c)
        self.assertNotIsInstance(flob, c)

    def test_with_default_args(self):
        c = Callable[[int], int]

        def flub(a: int, b: float = 3.14) -> int:
            return a

        def flab(a: int, *, b: float = 3.14) -> int:
            return a

        def flob(a: int = 42) -> int:
            return a

        self.assertIsInstance(flub, c)
        self.assertIsInstance(flab, c)
        self.assertIsInstance(flob, c)

    def test_with_varargs(self):
        c = Callable[[int], int]

        def flub(*args) -> int:
            return 42

        def flab(*args: int) -> int:
            return 42

        def flob(*args: float) -> int:
            return 42

        self.assertIsInstance(flub, c)
        self.assertIsInstance(flab, c)
        self.assertNotIsInstance(flob, c)

    def test_with_method(self):

        class C:

            def imethod(self, arg: int) -> int:
                self.last_arg = arg
                return arg + 1

            @classmethod
            def cmethod(cls, arg: int) -> int:
                cls.last_cls_arg = arg
                return arg + 1

            @staticmethod
            def smethod(arg: int) -> int:
                return arg + 1

        ct = Callable[[int], int]
        self.assertIsInstance(C().imethod, ct)
        self.assertIsInstance(C().cmethod, ct)
        self.assertIsInstance(C.cmethod, ct)
        self.assertIsInstance(C().smethod, ct)
        self.assertIsInstance(C.smethod, ct)
        self.assertIsInstance(C.imethod, Callable[[Any, int], int])

    def test_cannot_subclass(self):
        with self.assertRaises(TypeError):

            class C(Callable):
                pass

        with self.assertRaises(TypeError):

            class C(Callable[[int], int]):
                pass

    def test_cannot_instantiate(self):
        with self.assertRaises(TypeError):
            Callable()
        c = Callable[[int], str]
        with self.assertRaises(TypeError):
            c()

    def test_callable_varargs(self):
        ct = Callable[..., int]

        def foo(a, b) -> int:
            return 42

        def bar(a=42) -> int:
            return a

        def baz(*, x, y, z) -> int:
            return 100

        self.assertIsInstance(foo, ct)
        self.assertIsInstance(bar, ct)
        self.assertIsInstance(baz, ct)


XK = TypeVar('XK', str, bytes)
XV = TypeVar('XV')


class SimpleMapping(Generic[XK, XV]):

    def __getitem__(self, key: XK) -> XV:
        ...

    def __setitem__(self, key: XK, value: XV):
        ...

    def get(self, key: XK, default: XV = None) -> XV:
        ...


class MySimpleMapping(SimpleMapping):

    def __init__(self):
        self.store = {}

    def __getitem__(self, key: str):
        return self.store[key]

    def __setitem__(self, key: str, value):
        self.store[key] = value

    def get(self, key: str, default=None):
        try:
            return self.store[key]
        except KeyError:
            return default


class ProtocolTests(TestCase):

    def test_supports_int(self):
        assert issubclass(int, typing.SupportsInt)
        assert not issubclass(str, typing.SupportsInt)

    def test_supports_float(self):
        assert issubclass(float, typing.SupportsFloat)
        assert not issubclass(str, typing.SupportsFloat)

    def test_supports_abs(self):
        assert issubclass(float, typing.SupportsAbs)
        assert issubclass(int, typing.SupportsAbs)
        assert not issubclass(str, typing.SupportsAbs)

    def test_supports_round(self):
        assert issubclass(float, typing.SupportsRound)
        assert issubclass(int, typing.SupportsRound)
        assert not issubclass(str, typing.SupportsRound)

    def test_reversible(self):
        assert issubclass(list, typing.Reversible)
        assert not issubclass(int, typing.Reversible)


class GenericTests(TestCase):

    def test_basics(self):
        X = SimpleMapping[str, Any]
        Y = SimpleMapping[AnyStr, str]
        X[str, str]
        Y[str, str]
        with self.assertRaises(TypeError):
            X[int, str]
        with self.assertRaises(TypeError):
            Y[str, bytes]

    def test_repr(self):
        self.assertEqual(repr(SimpleMapping),
                         __name__ + '.' + 'SimpleMapping[~XK, ~XV]')
        self.assertEqual(repr(MySimpleMapping),
                         __name__ + '.' + 'MySimpleMapping[~XK, ~XV]')
        A = TypeVar('A', str)  # Must be a subclass of XK.
        B = TypeVar('B')

        class X(SimpleMapping[A, B]):
            pass

        self.assertEqual(repr(X).split('.')[-1], 'X[~A, ~B]')

    def test_errors(self):
        with self.assertRaises(TypeError):
            B = SimpleMapping[XK, Any]

            class C(Generic[B]):
                pass

    def test_repr_2(self):
        PY32 = sys.version_info[:2] < (3, 3)

        class C(Generic[T]):
            pass

        assert C.__module__ == __name__
        if not PY32:
            assert C.__qualname__ == 'GenericTests.test_repr_2.<locals>.C'
        assert repr(C).split('.')[-1] == 'C[~T]'
        X = C[int]
        assert X.__module__ == __name__
        if not PY32:
            assert X.__qualname__ == 'C'
        assert repr(X).split('.')[-1] == 'C[int]'

        class Y(C[int]):
            pass

        assert Y.__module__ == __name__
        if not PY32:
            assert Y.__qualname__ == 'GenericTests.test_repr_2.<locals>.Y'
        assert repr(Y).split('.')[-1] == 'Y[int]'

    def test_eq_1(self):
        assert Generic == Generic
        assert Generic[T] == Generic[T]
        assert Generic[KT] != Generic[VT]

    def test_eq_2(self):

        class A(Generic[T]):
            pass

        class B(Generic[T]):
            pass

        assert A == A
        assert A != B
        assert A[T] == A[T]
        assert A[T] != B[T]

    def test_multiple_inheritance(self):

        class A(Generic[T, VT]):
            pass

        class B(Generic[KT, T]):
            pass

        class C(A, Generic[KT, VT], B):
            pass

        assert C.__parameters__ == (T, VT, KT)

    def test_nested(self):

        class G(Generic):
            pass

        class Visitor(G[T]):

            a = None

            def set(self, a: T):
                self.a = a

            def get(self):
                return self.a

            def visit(self) -> T:
                return self.a

        V = Visitor[typing.List[int]]

        class IntListVisitor(V):

            def append(self, x: int):
                self.a.append(x)

        a = IntListVisitor()
        a.set([])
        a.append(1)
        a.append(42)
        assert a.get() == [1, 42]


class UndefinedTest(TestCase):

    def test_basics(self):
        x = Undefined(int)
        x = Undefined(Any)
        x = Undefined(Union[int, str])
        x = Undefined(None)

    def test_errors(self):
        with self.assertRaises(TypeError):
            x = Undefined(42)
        u = Undefined(int)
        with self.assertRaises(TypeError):
            {u: 42}

    def test_repr(self):
        self.assertEqual(repr(Undefined(Any)), 'typing.Undefined(typing.Any)')

    def test_type_alias(self):
        # These simply must not fail.
        Undefined(typing.re.Pattern)
        Undefined(typing.re.Pattern[str])
        Undefined(typing.re.Pattern[bytes])
        Undefined(typing.re.Pattern[Any])


class CastTest(TestCase):

    def test_basics(self):
        assert cast(int, 42) == 42
        assert cast(float, 42) == 42
        assert type(cast(float, 42)) is int
        assert cast(Any, 42) == 42
        assert cast(list, 42) == 42
        assert cast(Union[str, float], 42) == 42
        assert cast(AnyStr, 42) == 42
        assert cast(None, 42) == 42

    def test_errors(self):
        # Bogus calls are not expected to fail.
        cast(42, 42)
        cast('hello', 42)


class ForwardRefTest(TestCase):

    def test_basics(self):

        class Node(Generic[T]):

            def __init__(self, label: T):
                self.label = label
                self.left = self.right = None

            def add_both(self,
                         left: 'Optional[Node[T]]',
                         right: 'Node[T]' = None,
                         stuff: int = None,
                         blah=None):
                self.left = left
                self.right = right

            def add_left(self, node: Optional['Node[T]']):
                self.add_both(node, None)

            def add_right(self, node: 'Node[T]' = None):
                self.add_both(None, node)

        t = Node[int]
        both_hints = get_type_hints(t.add_both)
        assert both_hints['left'] == both_hints['right'] == Optional[Node[T]]
        assert both_hints['stuff'] == Optional[int]
        assert 'blah' not in both_hints

        left_hints = get_type_hints(t.add_left)
        assert left_hints['node'] == Optional[Node[T]]

        right_hints = get_type_hints(t.add_right)
        assert right_hints['node'] == Optional[Node[T]]

    def test_union_forward(self):

        def foo(a: Union['T']):
            pass

        self.assertEqual(get_type_hints(foo), {'a': Union[T]})

    def test_tuple_forward(self):

        def foo(a: Tuple['T']):
            pass

        self.assertEqual(get_type_hints(foo), {'a': Tuple[T]})

    def test_callable_forward(self):

        def foo(a: Callable[['T'], 'T']):
            pass

        self.assertEqual(get_type_hints(foo), {'a': Callable[[T], T]})

    def test_syntax_error(self):

        with self.assertRaises(SyntaxError):
            Generic['/T']

    def test_delayed_syntax_error(self):

        def foo(a: 'Node[T'):
            pass

        with self.assertRaises(SyntaxError):
            get_type_hints(foo)

    def test_name_error(self):

        def foo(a: 'Noode[T]'):
            pass

        with self.assertRaises(NameError):
            get_type_hints(foo)

    def test_no_type_check(self):

        @no_type_check
        def foo(a: 'whatevers') -> {}:
            pass

        th = get_type_hints(foo)
        self.assertEqual(th, {})

    def test_meta_no_type_check(self):

        @no_type_check_decorator
        def magic_decorator(deco):
            return deco

        self.assertEqual(magic_decorator.__name__, 'magic_decorator')

        @magic_decorator
        def foo(a: 'whatevers') -> {}:
            pass

        self.assertEqual(foo.__name__, 'foo')
        th = get_type_hints(foo)
        self.assertEqual(th, {})


class OverloadTests(TestCase):

    def test_overload_exists(self):
        from typing import overload

    def test_overload_fails(self):
        from typing import overload

        with self.assertRaises(RuntimeError):
            @overload
            def blah():
                pass


class CollectionsAbcTests(TestCase):

    def test_hashable(self):
        assert isinstance(42, typing.Hashable)
        assert not isinstance([], typing.Hashable)

    def test_iterable(self):
        assert isinstance([], typing.Iterable)
        assert isinstance([], typing.Iterable[int])
        assert not isinstance(42, typing.Iterable)

    def test_iterator(self):
        it = iter([])
        assert isinstance(it, typing.Iterator)
        assert isinstance(it, typing.Iterator[int])
        assert not isinstance(42, typing.Iterator)

    def test_sized(self):
        assert isinstance([], typing.Sized)
        assert not isinstance(42, typing.Sized)

    def test_container(self):
        assert isinstance([], typing.Container)
        assert not isinstance(42, typing.Container)

    def test_abstractset(self):
        assert isinstance(set(), typing.AbstractSet)
        assert not isinstance(42, typing.AbstractSet)

    def test_mutableset(self):
        assert isinstance(set(), typing.MutableSet)
        assert not isinstance(frozenset(), typing.MutableSet)

    def test_mapping(self):
        assert isinstance({}, typing.Mapping)
        assert not isinstance(42, typing.Mapping)

    def test_mutablemapping(self):
        assert isinstance({}, typing.MutableMapping)
        assert not isinstance(42, typing.MutableMapping)

    def test_sequence(self):
        assert isinstance([], typing.Sequence)
        assert not isinstance(42, typing.Sequence)

    def test_mutablesequence(self):
        assert isinstance([], typing.MutableSequence)
        assert not isinstance((), typing.MutableSequence)

    def test_bytestring(self):
        assert isinstance(b'', typing.ByteString)
        assert isinstance(bytearray(b''), typing.ByteString)

    def test_list(self):
        assert issubclass(list, typing.List)
        assert isinstance([], typing.List)
        assert not isinstance((), typing.List)
        t = typing.List[int]
        assert isinstance([], t)
        assert isinstance([42], t)
        assert not isinstance([''], t)

    def test_set(self):
        assert issubclass(set, typing.Set)
        assert isinstance(set(), typing.Set)
        assert not isinstance({}, typing.Set)
        t = typing.Set[int]
        assert isinstance(set(), t)
        assert isinstance({42}, t)
        assert not isinstance({''}, t)

    def test_mapping_views(self):
        # TODO: These tests are kind of lame.
        assert isinstance({}.keys(), typing.KeysView)
        assert isinstance({}.items(), typing.ItemsView)
        assert isinstance({}.values(), typing.ValuesView)

    def test_dict(self):
        assert issubclass(dict, typing.Dict)
        assert isinstance({}, typing.Dict)
        assert not isinstance([], typing.Dict)
        t = typing.Dict[int, str]
        assert isinstance({}, t)
        assert isinstance({42: ''}, t)
        assert not isinstance({42: 42}, t)
        assert not isinstance({'': 42}, t)
        assert not isinstance({'': ''}, t)


class NamedTupleTests(TestCase):

    def test_basics(self):
        Emp = NamedTuple('Emp', [('name', str), ('id', int)])
        assert issubclass(Emp, tuple)
        joe = Emp('Joe', 42)
        jim = Emp(name='Jim', id=1)
        assert isinstance(joe, Emp)
        assert isinstance(joe, tuple)
        assert joe.name == 'Joe'
        assert joe.id == 42
        assert jim.name == 'Jim'
        assert jim.id == 1
        assert Emp.__name__ == 'Emp'
        assert Emp._fields == ('name', 'id')
        assert Emp._field_types == dict(name=str, id=int)


class IOTests(TestCase):

    def test_io(self):

        def stuff(a: IO) -> AnyStr:
            return a.readline()

        a = stuff.__annotations__['a']
        assert a.__parameters__ == (AnyStr,)

    def test_textio(self):

        def stuff(a: TextIO) -> str:
            return a.readline()

        a = stuff.__annotations__['a']
        assert a.__parameters__ == (str,)

    def test_binaryio(self):

        def stuff(a: BinaryIO) -> bytes:
            return a.readline()

        a = stuff.__annotations__['a']
        assert a.__parameters__ == (bytes,)

    def test_io_submodule(self):
        from typing.io import IO, TextIO, BinaryIO, __all__, __name__
        assert IO is typing.IO
        assert TextIO is typing.TextIO
        assert BinaryIO is typing.BinaryIO
        assert set(__all__) == set(['IO', 'TextIO', 'BinaryIO'])
        assert __name__ == 'typing.io'


class RETests(TestCase):
    # Much of this is really testing _TypeAlias.

    def test_basics(self):
        pat = re.compile('[a-z]+', re.I)
        assert isinstance(pat, Pattern)
        assert isinstance(pat, Pattern[str])
        assert not isinstance(pat, Pattern[bytes])
        assert issubclass(type(pat), Pattern)
        assert issubclass(type(pat), Pattern[str])

        mat = pat.search('12345abcde.....')
        assert isinstance(mat, Match)
        assert isinstance(mat, Match[str])
        assert not isinstance(mat, Match[bytes])
        assert issubclass(type(mat), Match)
        assert issubclass(type(mat), Match[str])

        p = Pattern[Union[str, bytes]]
        assert isinstance(pat, p)
        assert issubclass(Pattern[str], Pattern)
        assert issubclass(Pattern[str], p)

        m = Match[Union[bytes, str]]
        assert isinstance(mat, m)
        assert issubclass(Match[bytes], Match)
        assert issubclass(Match[bytes], m)

    def test_errors(self):
        with self.assertRaises(TypeError):
            # Doesn't fit AnyStr.
            Pattern[int]
        with self.assertRaises(TypeError):
            # Can't change type vars?
            Match[T]
        m = Match[Union[str, bytes]]
        with self.assertRaises(TypeError):
            # Too complicated?
            m[str]

    def test_repr(self):
        assert repr(Pattern) == 'Pattern[~AnyStr]'
        assert repr(Pattern[str]) == 'Pattern[str]'
        assert repr(Pattern[bytes]) == 'Pattern[bytes]'
        assert repr(Match) == 'Match[~AnyStr]'
        assert repr(Match[str]) == 'Match[str]'
        assert repr(Match[bytes]) == 'Match[bytes]'

    def test_re_submodule(self):
        from typing.re import Match, Pattern, __all__, __name__
        assert Match is typing.Match
        assert Pattern is typing.Pattern
        assert set(__all__) == set(['Match', 'Pattern'])
        assert __name__ == 'typing.re'


class AllTests(TestCase):
    """Tests for __all__."""

    def test_all(self):
        from typing import __all__ as a
        # Don't test everything, just spot-check the first and last of every category.
        assert 'AbstractSet' in a
        assert 'ValuesView' in a
        assert 'POSIX' in a
        assert 'WINDOWS' in a
        assert 'cast' in a
        assert 'overload' in a
        assert 'io' in a
        assert 're' in a
        # Spot-check that stdlib modules aren't exported.
        assert 'os' not in a
        assert 'sys' not in a


if __name__ == '__main__':
    main()
