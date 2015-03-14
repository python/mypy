from __future__ import with_statement, unicode_literals
from abc import abstractmethod, ABCMeta
import unittest

from typing import (
    List, Dict, Set, Tuple, Pattern, Match, Any, Callable, Generic,
    _Protocol, Sized, Iterable, Iterator, Sequence, Union, Optional,
    AbstractSet, Mapping, BinaryIO, TextIO, SupportsInt, SupportsFloat,
    SupportsAbs, Reversible, Undefined, AnyStr, annotations,
    cast, overload, TypeVar
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
        self.assertIs(type(re.compile('')), Pattern[unicode])
        self.assertIs(type(re.compile(b'')), Pattern[str])

    def test_Match(self):
        import re
        self.assertIs(type(re.match('', '')), Match[unicode])
        self.assertIs(type(re.match(b'', b'')), Match[str])

    def test_Any(self):
        o = object()
        self.assertIs(Any(o), o)
        s = 'x'
        self.assertIs(Any(s), s)

    def test_Callable(self):
        # Just check that we can call Callable. Don't care about return value.
        Callable[[], int]
        Callable[[int], None]
        Callable[[int, unicode], bool]

    def test_cast(self):
        o = object()
        # cast performs no runtime checks!
        self.assertIs(cast(int, o), o)
        s = 'x'
        self.assertIs(cast(unicode, s), s)
        self.assertIs(cast('xyz', s), s)
        # cast does not check type validity; anything goes.
        self.assertIs(cast(o, s), s)

    def test_annotations(self):
        @annotations(x=int, returns=unicode)
        def f(x): return 'string'

        self.assertEqual(f.__annotations__, {'x': int, 'return': unicode})

    def test_typevar(self):
        t = TypeVar('t')
        self.assertEqual(t.name, 't')
        self.assertIsNone(t.values)

    def test_typevar_values(self):
        t = TypeVar('t', int, unicode)
        self.assertEqual(t.name, 't')
        self.assertEqual(t.values, (int, unicode))

    def test_predefined_typevars(self):
        self.assertEqual(AnyStr.name, 'AnyStr')
        self.assertEqual(AnyStr.values, (str, unicode))

    def test_simple_generic_class(self):
        t = TypeVar('t')

        class C(Generic[t]):
            pass

        self.assertIs(C[int], C)
        self.assertIsInstance(C(), C)
        self.assertIsInstance(C[int](), C)

    def test_generic_class_with_two_typeargs(self):
        t = TypeVar('t')
        u = TypeVar('u')

        class C(Generic[t, u]):
            pass

        self.assertIs(C[int, unicode], C)
        self.assertIsInstance(C(), C)
        self.assertIsInstance(C[int, unicode](), C)

    def test_abstract_generic_class(self):
        t = TypeVar('t')
        class C(Generic[t]):
            pass
        class D(object):
            pass
        self.assertNotIsInstance(D(), C)
        C.register(D)
        self.assertIsInstance(D(), C)

    def test_sequence(self):
        self.assertIs(Sequence[int], Sequence)

        self.assertIsInstance([], Sequence)
        self.assertIsInstance((), Sequence)
        self.assertIsInstance('', Sequence)
        self.assertIsInstance(b'', Sequence)
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
        self.assertNotIsInstance('', SupportsInt)
        self.assertNotIsInstance(b'', SupportsInt)
        self.assertNotIsInstance((), SupportsInt)

    def test_supports_float(self):
        self.assertIsInstance(1.1, SupportsFloat)
        self.assertIsInstance(1, SupportsFloat)
        self.assertNotIsInstance('', SupportsFloat)
        self.assertNotIsInstance(b'', SupportsFloat)
        self.assertNotIsInstance((), SupportsFloat)

    def test_supports_abs(self):
        self.assertIsInstance(1.1, SupportsAbs)
        self.assertIsInstance(1, SupportsAbs)
        self.assertNotIsInstance('', SupportsAbs)
        self.assertNotIsInstance((), SupportsAbs)

    def test_reversible(self):
        self.assertIsInstance([], Reversible)
        self.assertIsInstance(xrange(1), Reversible)
        self.assertNotIsInstance((), Reversible)
        self.assertNotIsInstance('', Reversible)

    def test_simple_protocol(self):
        class P(_Protocol):
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
        self.assertTrue(issubclass(P, _Protocol))
        self.assertTrue(issubclass(_Protocol, _Protocol))
        self.assertTrue(issubclass(A, _Protocol))

    def test_issubclass_of_protocol(self):
        class A(object): pass
        self.assertTrue(issubclass(A, _Protocol))

    def test_protocol_with_two_attrs(self):
        class P(_Protocol):
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
        class P(_Protocol):
            def f(self): pass
        class PP(P, _Protocol):
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

        class AA(_Protocol):
            def f(self): return 1
        class BB(AA): pass

        self.assertEqual(BB().f(), 1)

        class CC(AA): pass
        # BB is not a protocol since it doesn't explicitly subclass _Protocol.
        self.assertNotIsInstance(CC(), BB)

    def test_builtin_class_and_protocol(self):
        class P(_Protocol):
            def __add__(self): pass

        self.assertIsInstance('', P)
        self.assertIsInstance([], P)
        self.assertIsInstance(1, P)
        self.assertNotIsInstance({}, P)

        self.assertTrue(issubclass(unicode, P))
        self.assertFalse(issubclass(dict, P))

    def test_generic_protocol(self):
        t = TypeVar('t')
        class P(_Protocol[t]):
            x = 1
        class A(object):
            x = 2
        self.assertIsInstance(A(), P)

    def test_indexing_in_protocol(self):
        class P(_Protocol):
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
        self.assertIsInstance('', Sized)
        self.assertIsInstance(b'', Sized)
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
        self.assertIsInstance(iter(''), Iterator)
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
        class P(_Protocol):
            x = 1
        class P2(_Protocol):
            y = 1
        class P3(P, P2, _Protocol): pass

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
        class P(_Protocol):
            u"""blah"""
            def f(self): pass
        class A(object):
            def f(self): pass
        self.assertIsInstance(A(), P)

    def test_string_literal_in_annotation(self):
        @annotations(a='unicode', returns='unicode')
        def f(a):
            return a + 'x'
        @annotations(a='Iterable[int]', returns='List[int]')
        def f(a):
            return list(a)

    def test_undefined(self):
        self.assertEqual(unicode(Undefined), '<typing.Undefined>')
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

    def test_construct_class_with_abstract_method(self):
        t = TypeVar('t')

        class A(Generic[t]):
            @abstractmethod
            def f(self): pass

        class B(A):
            def f(self): pass

        with self.assertRaises(TypeError):
            A()
        B()

    def test_protocol_with_abstract_method(self):
        class A(_Protocol):
            @abstractmethod
            def f(self): pass

        with self.assertRaises(TypeError):
            A()  # No implementation for abstract method.

    def test_protocol_inheritance_with_abstract_method(self):
        class A(_Protocol):
            @abstractmethod
            def f(self): pass
        class B(A):
            pass

        with self.assertRaises(TypeError):
            B()  # No implementation for abstract method.
        class C(A):
            def f(self): pass
        C()

    def test_overload(self):
        with self.assertRaises(RuntimeError):
            @overload
            def f(): pass
        with self.assertRaises(RuntimeError):
            @overload
            def g(x): pass
        with self.assertRaises(RuntimeError):
            @overload
            def h(x): pass
            @overload
            def h(x): pass

    def test_optional(self):
        # TODO: This test actually isn't very useful right now, but it will make sense
        #       once Union is modified to keep track of the given type arguments.
        self.assertEqual(Optional[int], Union[int, None])


class Dummy(object):
    u"""Dummy class defined in module scope"""


if __name__ == '__main__':
    unittest.main()
