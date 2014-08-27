from __future__ import with_statement
from abc import abstractmethod, ABCMeta
import unittest

from typing import (
    List, Dict, Set, Tuple, Pattern, BytesPattern, Match, BytesMatch, Any,
    Function, Generic, AbstractGeneric, Protocol, Sized, Iterable, Iterator,
    Sequence, AbstractSet, Mapping, BinaryIO, TextIO, SupportsInt, SupportsFloat,
    SupportsAbs, Reversible, Undefined, cast, forwardref, overload, typevar
)


class TestTyping(unittest.TestCase):
    def test_List(self):
        self.assertIs(List[int], list)
        self.assertIs(List[unicode], list)

    def test_Dict(self):
        self.assertIs(Dict[int, unicode], dict)
        self.assertIs(Dict[unicode, int], dict)

    def test_Set(self):
        self.assertIs(Set[int], set)
        self.assertIs(Set[unicode], set)

    def test_Tuple(self):
        self.assertIs(Tuple[int], tuple)
        self.assertIs(Tuple[unicode, int], tuple)
        self.assertIs(Tuple[unicode, int, bool], tuple)

    def test_Pattern(self):
        import re
        self.assertIs(type(re.compile(u'')), Pattern)
        self.assertIs(type(re.compile('')), BytesPattern)
        # Note that actually Pattern is the same as BytesPattern, which is
        # a bit awkward.

    def test_Match(self):
        import re
        self.assertIs(type(re.match(u'', u'')), Match)
        self.assertIs(type(re.match('', '')), BytesMatch)
        # Note that actually Match is the same as BytesMatch, which is
        # a bit awkward.

    def test_Any(self):
        o = object()
        self.assertIs(Any(o), o)
        s = u'x'
        self.assertIs(Any(s), s)

    def test_Function(self):
        # Just check that we can call Function. Don't care about return value.
        Function[[], int]
        Function[[int], None]
        Function[[int, unicode], bool]

    def test_cast(self):
        o = object()
        # cast performs no runtime checks!
        self.assertIs(cast(int, o), o)
        s = u'x'
        self.assertIs(cast(unicode, s), s)
        self.assertIs(cast(u'xyz', s), s)
        # cast does not check type validity; anything goes.
        self.assertIs(cast(o, s), s)

    @unittest.skip("overloads not supported in 2.7 yet")
    def test_simple_overload(self):
        @overload
        def f(x): return x + u'string'
        @overload
        def f(x): return x + 1

        self.assertEqual(f(u'x'), u'xstring')
        self.assertEqual(f(1), 2)

        @overload
        def g(x): return u'integer'
        @overload
        def g(x): return u'string'

        self.assertEqual(g(u'x'), u'string')
        self.assertEqual(g(1), u'integer')

    @unittest.skip("overloads not supported in 2.7 yet")
    def test_overload_with_three_variants(self):
        @overload
        def f(x): return u'string'
        @overload
        def f(x): return u'integer'
        @overload
        def f(x): return u'floating'

        self.assertEqual(f(u'x'), u'string')
        self.assertEqual(f(1), u'integer')
        self.assertEqual(f(1.0), u'floating')

    @unittest.skip("overloads not supported in 2.7 yet")
    def test_overload_with_two_args(self):
        @overload
        def f(x, y): return (1, x, y)
        @overload
        def f(x, y): return (2, x, y)

        self.assertEqual(f(u'x', u'y'), (1, u'x', u'y'))
        self.assertEqual(f(u'z', 3), (2, u'z', 3))

        @overload
        def g(x, y): return 1
        @overload
        def g(x, y): return 2

        self.assertEqual(g(u'x', u'y'), 1)
        self.assertEqual(g(u'x', 1), 2)

    @unittest.skip("overloads not supported in 2.7 yet")
    def test_global_overload(self):
        self.assertEqual(global_overload(u'x'), u's')
        self.assertEqual(global_overload(1), u'i')

    @unittest.skip("overloads not supported in 2.7 yet")
    def test_partial_overload_annotation(self):
        @overload
        def f(x, y): return 1
        @overload
        def f(x, y): return 2

        self.assertEqual(f(u'x', object()), 1)
        self.assertEqual(f(object(), 1), 2)

    @overload
    def method_overload(self, x):
        return u's'

    @overload
    def method_overload(self, x):
        return u'i'

    @unittest.skip("overloads not supported in 2.7 yet")
    def test_method_overload(self):
        self.assertEqual(self.method_overload(u'x'), u's')
        self.assertEqual(self.method_overload(1), u'i')

    @unittest.skip("overloads not supported in 2.7 yet")
    def test_overload_with_any_type(self):
        @overload
        def f(x, y): return 1
        @overload
        def f(x, y): return 2

        self.assertEqual(f((), 0), 1)
        self.assertEqual(f((), ()), 2)

    @unittest.skip("overloads not supported in 2.7 yet")
    def test_overload_with_type_alias(self):
        @overload
        def f(x): return 1
        @overload
        def f(x): return 2
        @overload
        def f(x): return 3
        @overload
        def f(x): return 4

        self.assertEqual(f([]), 1)
        self.assertEqual(f({}), 2)
        self.assertEqual(f(()), 3)
        self.assertEqual(f((1, u'x')), 3)
        self.assertEqual(f(1), 4)

    @unittest.skip("overloads not supported in 2.7 yet")
    def test_call_overload_with_invalid_arg_count(self):
        @overload
        def f(x): return 1
        @overload
        def f(x): return 2

        msg1 = ur'f\(\) takes exactly 1 argument \(%d given\)'
        msg2 = ur'f\(\) takes exactly 1 positional argument \(%d given\)'

        with self.assertRaisesRegex(TypeError, msg1 % 0):
            f()
        with self.assertRaisesRegex(TypeError, msg2 % 2):
            f(1, 2)
        with self.assertRaisesRegex(TypeError, msg2 % 3):
            f(u'x', u'y', u'z')

    @unittest.skip("overloads not supported in 2.7 yet")
    def test_overload_with_variable_argument_counts(self):
        @overload
        def f(): return None
        @overload
        def f(x): return x

        self.assertEqual(f(), None)
        self.assertEqual(f(1), 1)

        @overload
        def g(x): return x + 1
        @overload
        def g(): return None

        self.assertEqual(g(), None)
        self.assertEqual(g(1), 2)

        msg = ur'g\(\) takes no arguments \(2 given\)'
        with self.assertRaisesRegex(TypeError, msg):
            g(1, 2)

    @unittest.skip("overloads not supported in 2.7 yet")
    def test_overload_dispatch_order(self):
        class A(object): pass
        class B(A): pass
        class C(B): pass

        @overload
        def f(x): return u'B'
        @overload
        def f(x): return u'A'

        self.assertEqual(f(B()), u'B')
        self.assertEqual(f(A()), u'A')

        @overload
        def g(x): return u'C'
        @overload
        def g(x): return u'B'
        @overload
        def g(x): return u'A'

        self.assertEqual(g(C()), u'C')
        self.assertEqual(g(B()), u'B')
        self.assertEqual(g(A()), u'A')

    @unittest.skip("overloads not supported in 2.7 yet")
    def test_name_of_overloaded_function(self):
        @overload
        def f(x): return 1
        @overload
        def f(x): return 2

        self.assertEqual(f.__name__, u'f')

    @unittest.skip("overloads not supported in 2.7 yet")
    def test_overloaded_function_as_str(self):
        @overload
        def f(x): return 1
        @overload
        def f(x): return 2

        self.assertRegex(unicode(f), u'^<function f at.*>$')

    @unittest.skip("overloads not supported in 2.7 yet")
    def test_overload_with_default_arg_values(self):
        @overload
        def f(x=u'x'): return x + u'!'
        @overload
        def f(y): return y + 1

        self.assertEqual(f(), u'x!')
        self.assertEqual(f(u'y'), u'y!')
        self.assertEqual(f(3), 4)

        @overload
        def g(a, x=u'x', y=u'z'): return 1
        @overload
        def g(a, x=1): return 2

        self.assertEqual(g(1), 1)
        self.assertEqual(g(u'x'), 2)
        self.assertEqual(g(1, u'XX'), 1)
        self.assertEqual(g(1, 2), 2)
        self.assertEqual(g(1, u'XX', u'YY'), 1)

        with self.assertRaises(TypeError):
            g(1, u'x', 2)

    @unittest.skip("overloads not supported in 2.7 yet")
    def test_no_matching_overload(self):
        @overload
        def f(x): return 1
        @overload
        def f(x): return 2

        # Fall back to the last overload variant if no annotation matches.
        self.assertEqual(f(()), 2)

    @unittest.skip("overloads not supported in 2.7 yet")
    def test_function_type_dispatch_in_overload(self):
        @overload
        def f(x): return 1
        @overload
        def f(x): return 2

        self.assertEqual(f(ord), 1)
        self.assertEqual(f(unicode.find), 1)
        self.assertEqual(f(u'x'.find), 1)
        self.assertEqual(f(unicode), 1)
        self.assertEqual(f(TestTyping), 1)
        self.assertEqual(f(self.test_function_type_dispatch_in_overload), 1)
        self.assertEqual(f(self.assertEqual), 1)
        self.assertEqual(f(TestTyping.assertEqual), 1)

        class A(object):
            def __call__(self): pass

        self.assertEqual(f(A()), 1)

        self.assertEqual(f(1), 2)
        self.assertEqual(f(object()), 2)

    def test_typevar(self):
        t = typevar(u't')
        self.assertEqual(t.name, u't')

    @unittest.skip("overloads not supported in 2.7 yet")
    def test_typevar_in_overload(self):
        t = typevar(u't')

        @overload
        def f(x, y): return 1
        @overload
        def f(x, y): return 2

        self.assertEqual(f((), u'x'), 1)
        self.assertEqual(f((), 1.1), 2)

    def test_simple_generic_class(self):
        t = typevar(u't')

        class C(Generic[t]):
            pass

        self.assertIs(C[int], C)
        self.assertIsInstance(C(), C)
        self.assertIsInstance(C[int](), C)

    def test_generic_class_with_two_typeargs(self):
        t = typevar(u't')
        u = typevar(u'u')

        class C(Generic[t, u]):
            pass

        self.assertIs(C[int, unicode], C)
        self.assertIsInstance(C(), C)
        self.assertIsInstance(C[int, unicode](), C)

    def test_abstract_generic_class(self):
        t = typevar(u't')
        class C(AbstractGeneric[t]):
            pass
        class D(object):
            pass
        self.assertIs(C[int], C)
        self.assertNotIsInstance(D(), C)
        C.register(D)
        self.assertIsInstance(D(), C)

    def test_sequence(self):
        self.assertIs(Sequence[int], Sequence)

        self.assertIsInstance([], Sequence)
        self.assertIsInstance((), Sequence)
        self.assertIsInstance(u'', Sequence)
        self.assertIsInstance('', Sequence)
        self.assertIsInstance(xrange(5), Sequence)
        self.assertNotIsInstance({}, Sequence)

    def test_abstract_set(self):
        self.assertIs(AbstractSet[int], AbstractSet)

        self.assertIsInstance(set(), AbstractSet)
        self.assertIsInstance(frozenset(), AbstractSet)

    def test_mapping(self):
        self.assertIs(Mapping[int, unicode], Mapping)
        self.assertIsInstance({}, Mapping)

    def test_io_types(self):
        self.assertIsInstance(BinaryIO, type)
        self.assertIsInstance(TextIO, type)

    def test_supports_int(self):
        self.assertIsInstance(1, SupportsInt)
        self.assertIsInstance(1.1, SupportsInt)
        self.assertNotIsInstance(u'', SupportsInt)
        self.assertNotIsInstance('', SupportsInt)
        self.assertNotIsInstance((), SupportsInt)

    def test_supports_float(self):
        self.assertIsInstance(1.1, SupportsFloat)
        self.assertIsInstance(1, SupportsFloat)
        self.assertNotIsInstance(u'', SupportsFloat)
        self.assertNotIsInstance('', SupportsFloat)
        self.assertNotIsInstance((), SupportsFloat)

    def test_supports_abs(self):
        self.assertIsInstance(1.1, SupportsAbs)
        self.assertIsInstance(1, SupportsAbs)
        self.assertNotIsInstance(u'', SupportsAbs)
        self.assertNotIsInstance((), SupportsAbs)

    def test_reversible(self):
        self.assertIsInstance([], Reversible)
        self.assertIsInstance(xrange(1), Reversible)
        self.assertNotIsInstance((), Reversible)
        self.assertNotIsInstance(u'', Reversible)

    def test_simple_protocol(self):
        class P(Protocol):
            def f(self): pass

        class A(object):
            # Conforms to P
            def f(self): pass
            def g(self): pass

        class B(object):
            # Does not conform to P
            def g(self): pass

        self.assertIsInstance(A(), P)
        self.assertNotIsInstance(B(), P)

        self.assertTrue(issubclass(A, P))
        self.assertFalse(issubclass(B, P))
        self.assertTrue(issubclass(P, Protocol))
        self.assertTrue(issubclass(Protocol, Protocol))
        self.assertTrue(issubclass(A, Protocol))

    def test_issubclass_of_protocol(self):
        class A(object): pass
        self.assertTrue(issubclass(A, Protocol))

    def test_protocol_with_two_attrs(self):
        class P(Protocol):
            def __int__(self): pass
            x = 0

        class A(object):
            # Conforms to P; attribute values don't need to be similar
            __int__ = 0
            def x(self): pass
            def f(self): pass  # Extra method

        class B(object):
            # Does not conform to P
            __int__ = 0
        class C(object):
            # Does not conform to P
            x = 0

        self.assertIsInstance(A(), P)
        self.assertNotIsInstance(B(), P)
        self.assertNotIsInstance(C(), P)

    def test_protocol_inheritance(self):
        class P(Protocol):
            def f(self): pass
        class PP(P, Protocol):
            def g(self): pass

        class A(object):
            # Conforms to P but not PP
            def f(self): pass
        class B(object):
            # Conforms to P and PP
            def f(self): pass
            def g(self): pass
        class C(object):
            # Conforms to neither P nor PP
            def g(self): pass

        self.assertIsInstance(A(), P)
        self.assertIsInstance(B(), P)
        self.assertIsInstance(B(), PP)
        self.assertNotIsInstance(A(), PP)
        self.assertNotIsInstance(C(), PP)

    def test_builtin_class_and_protocol(self):
        class P(Protocol):
            def __add__(self): pass

        self.assertIsInstance(u'', P)
        self.assertIsInstance([], P)
        self.assertIsInstance(1, P)
        self.assertNotIsInstance({}, P)

        self.assertTrue(issubclass(unicode, P))
        self.assertFalse(issubclass(dict, P))

    def test_generic_protocol(self):
        t = typevar(u't')
        class P(Protocol[t]):
            x = 1
        class A(object):
            x = 2
        self.assertIsInstance(A(), P)

    def test_indexing_in_protocol(self):
        class P(Protocol):
            def __getitem__(self): pass
        class A(object):
            def __getitem__(self): pass
        class B(object):
            pass
        self.assertIsInstance(A(), P)
        self.assertNotIsInstance(B(), P)

    def test_sized(self):
        self.assertIsInstance([], Sized)
        self.assertIsInstance((), Sized)
        self.assertIsInstance(u'', Sized)
        self.assertIsInstance('', Sized)
        self.assertIsInstance({}, Sized)
        self.assertIsInstance(set(), Sized)
        self.assertIsInstance(xrange(5), Sized)
        self.assertNotIsInstance(1, Sized)

        class A(object):
            def __len__(self): pass

        self.assertIsInstance(A(), Sized)

    def test_iterable(self):
        self.assertIsInstance([], Iterable)
        class A(object):
            def __iter__(self): pass
            def g(self): pass
        self.assertIsInstance(A(), Iterable)
        self.assertNotIsInstance(1, Iterable)

    def test_iterator(self):
        self.assertIsInstance(iter(u''), Iterator)
        self.assertIsInstance(iter([]), Iterator)
        self.assertIsInstance(iter({}), Iterator)
        self.assertNotIsInstance([], Iterator)

        class A(object):
            def __iter__(self): pass
            def next(self): pass
        self.assertIsInstance(A(), Iterator)

        class B(object):
            def __iter__(self): pass
        self.assertNotIsInstance(B(), Iterator)

        class C(object):
            def next(self): pass
        self.assertNotIsInstance(C(), Iterator)

    def test_class_inheritance_and_protocols(self):
        class A(object):
            def __iter__(self): pass
        class B(A):
            def next(self): pass
        self.assertIsInstance(B(), Iterator)
        self.assertNotIsInstance(A(), Iterator)

    def test_class_multiple_inheritance_and_protocols(self):
        class A(object):
            def __iter__(self): pass
        class B(object):
            def next(self): pass
        class C(A, B): pass
        self.assertIsInstance(C(), Iterator)
        self.assertNotIsInstance(A(), Iterator)
        self.assertNotIsInstance(B(), Iterator)

    def test_multiple_protocol_inheritance(self):
        class P(Protocol):
            x = 1
        class P2(Protocol):
            y = 1
        class P3(P, P2, Protocol): pass

        class A(object):
            x = 1
            y = 1
        class B(object):
            x = 1
        class C(object):
            y = 1

        self.assertIsInstance(A(), P3)
        self.assertNotIsInstance(B(), P3)
        self.assertNotIsInstance(C(), P3)

    def test_protocol_docstrings(self):
        class P(Protocol):
            u"""blah"""
            def f(self): pass
        class A(object):
            def f(self): pass
        self.assertIsInstance(A(), P)

    def test_forward_ref_in_annotation(self):
        A = forwardref(u'A')
        def f(a):
            return a
        self.assertEqual(A.name, u'A')
        class A(object): pass

    def test_string_literal_in_annotation(self):
        def f(a):
            return a + u'x'
        def f(a):
            return list(a)

    def test_undefined(self):
        self.assertEqual(unicode(Undefined), u'<typing.Undefined>')
        with self.assertRaises(AttributeError):
            Undefined.x = 1
        with self.assertRaises(AttributeError):
            Undefined.x
        with self.assertRaises(TypeError):
            if Undefined == 0: pass
        with self.assertRaises(TypeError):
            if Undefined != 0: pass
        with self.assertRaises(TypeError):
            hash(Undefined)
        with self.assertRaises(TypeError):
            if Undefined: pass
        with self.assertRaises(TypeError):
            if not Undefined: pass

    @unittest.skip("overloads not supported in 2.7 yet")
    def test_simple_string_literal_in_overload(self):
        @overload
        def f(a): return u's'
        @overload
        def f(a): return u'i'

        self.assertEqual(f(u''), u's')
        self.assertEqual(f(2), u'i')

    @unittest.skip("overloads not supported in 2.7 yet")
    def test_module_ref_string_literal_in_overload(self):
        @overload
        def f(a): return 1
        @overload
        def f(a): return 2

        self.assertEqual(f(Dummy()), 1)
        self.assertEqual(f(2), 2)

    @unittest.skip("overloads not supported in 2.7 yet")
    def test_module_ref_string_literal_in_overload(self):
        @overload
        def f(a): return 1
        @overload
        def f(a): return 2

        self.assertEqual(f(Dummy()), 1)
        self.assertEqual(f(2), 2)

    @unittest.skip("overloads not supported in 2.7 yet")
    def test_local_ref_string_literal_in_overload(self):
        @overload
        def f(a): return 1
        @overload
        def f(a): return 2

        class C(object): pass
        self.assertEqual(f(C()), 1)
        self.assertEqual(f(2), 2)

    @unittest.skip("overloads not supported in 2.7 yet")
    def test_any_string_literal_in_overload(self):
        @overload
        def f(a): return 1
        @overload
        def f(a): return 2

        self.assertEqual(f(object()), 1)
        self.assertEqual(f(None), 1)

    @unittest.skip("overloads not supported in 2.7 yet")
    def test_generic_type_string_literal_in_overload(self):
        @overload
        def f(a): return 1
        @overload
        def f(a): return 2

        self.assertEqual(f([]), 1)
        self.assertEqual(f(()), 2)

    @unittest.skip("overloads not supported in 2.7 yet")
    def test_tuple_type_string_literal_in_overload(self):
        @overload
        def f(a): return 1
        @overload
        def f(a): return 2

        self.assertEqual(f(()), 1)
        self.assertEqual(f([]), 2)

    @unittest.skip("overloads not supported in 2.7 yet")
    def test_function_type_string_literal_in_overload(self):
        @overload
        def f(a): return 1
        @overload
        def f(a): return 2

        self.assertEqual(f(ord), 1)
        self.assertEqual(f([]), 2)

    @unittest.skip("overloads not supported in 2.7 yet")
    def test_forward_ref_in_overload(self):
        A = forwardref(u'A')

        @overload
        def f(a): return 1
        @overload
        def f(a): return 2

        class A(object): pass

        self.assertEqual(f(A()), 1)
        self.assertEqual(f(object()), 2)

    def test_construct_class_with_abstract_method(self):
        t = typevar(u't')

        class A(AbstractGeneric[t]):
            @abstractmethod
            def f(self): pass

        class B(A):
            def f(self): pass

        with self.assertRaises(TypeError):
            A()
        B()

    def test_protocol_with_abstract_method(self):
        class A(Protocol):
            @abstractmethod
            def f(self): pass

        with self.assertRaises(TypeError):
            A()  # No implementation for abstract method.

    def test_protocol_inheritance(self):
        class A(Protocol):
            def f(self): return 1
        class B(A): pass

        self.assertEqual(B().f(), 1)

        class C(A): pass
        # B is not a protocol since it doesn't explicitly subclass Protocol.
        self.assertNotIsInstance(C(), B)

    def test_protocol_inheritance_with_abstract_method(self):
        class A(Protocol):
            @abstractmethod
            def f(self): pass
        class B(A):
            pass

        with self.assertRaises(TypeError):
            B()  # No implementation for abstract method.
        class C(A):
            def f(self): pass
        C()

    @unittest.skip("overloads not supported in 2.7 yet")
    def test_overloaded_abstract_method(self):
        class A():
            __metaclass__ = ABCMeta
            @abstractmethod
            @overload
            def f(self, x): pass
            @abstractmethod
            @overload
            def f(self, x): pass

        with self.assertRaises(TypeError):
            A()

        class B():
            __metaclass__ = ABCMeta
            @overload
            @abstractmethod
            def f(self, x): pass

            @overload
            @abstractmethod
            def f(self, x): pass

        with self.assertRaises(TypeError):
            B()

        class C(B):
            @overload
            def f(self, x):
                return 1

            @overload
            def f(self, x):
                return u'x'

        self.assertEqual(C().f(2), 1)
        self.assertEqual(C().f(None), u'x')


@overload
def global_overload(x):
    return u's'


@overload
def global_overload(x):
    return u'i'


class Dummy(object):
    u"""Dummy class defined in module scope"""


if __name__ == u'__main__':
    unittest.main()
