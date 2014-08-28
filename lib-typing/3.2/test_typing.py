from abc import abstractmethod, ABCMeta
import unittest

from typing import (
    List, Dict, Set, Tuple, Pattern, Match, Any, Function, Generic,
    AbstractGeneric, Protocol, Sized, Iterable, Iterator, Sequence,
    AbstractSet, Mapping, BinaryIO, TextIO, SupportsInt, SupportsFloat,
    SupportsAbs, SupportsRound, Reversible, Undefined, AnyStr, builtinclass,
    cast, disjointclass, ducktype, forwardref, overload, typevar
)


class TestTyping(unittest.TestCase):
    def test_List(self):
        self.assertIs(List[int], list)
        self.assertIs(List[str], list)

    def test_Dict(self):
        self.assertIs(Dict[int, str], dict)
        self.assertIs(Dict[str, int], dict)

    def test_Set(self):
        self.assertIs(Set[int], set)
        self.assertIs(Set[str], set)

    def test_Tuple(self):
        self.assertIs(Tuple[int], tuple)
        self.assertIs(Tuple[str, int], tuple)
        self.assertIs(Tuple[str, int, bool], tuple)

    def test_Pattern(self):
        import re
        self.assertIs(type(re.compile('')), Pattern.target_type)
        self.assertIs(type(re.compile(b'')), Pattern.target_type)

    def test_Match(self):
        import re
        self.assertIs(type(re.match('', '')), Match.target_type)
        self.assertIs(type(re.match(b'', b'')), Match.target_type)

    def test_Any(self):
        o = object()
        self.assertIs(Any(o), o)
        s = 'x'
        self.assertIs(Any(s), s)

    def test_Function(self):
        # Just check that we can call Function. Don't care about return value.
        Function[[], int]
        Function[[int], None]
        Function[[int, str], bool]

    def test_cast(self):
        o = object()
        # cast performs no runtime checks!
        self.assertIs(cast(int, o), o)
        s = 'x'
        self.assertIs(cast(str, s), s)
        self.assertIs(cast('xyz', s), s)
        # cast does not check type validity; anything goes.
        self.assertIs(cast(o, s), s)

    def test_simple_overload(self):
        @overload
        def f(x:str) -> str: return x + 'string'
        @overload
        def f(x:int) -> str: return x + 1

        self.assertEqual(f('x'), 'xstring')
        self.assertEqual(f(1), 2)

        @overload
        def g(x:int) -> str: return 'integer'
        @overload
        def g(x:str) -> str: return 'string'

        self.assertEqual(g('x'), 'string')
        self.assertEqual(g(1), 'integer')

    def test_overload_with_three_variants(self):
        @overload
        def f(x:str) -> str: return 'string'
        @overload
        def f(x:int) -> str: return 'integer'
        @overload
        def f(x:float) -> str: return 'floating'

        self.assertEqual(f('x'), 'string')
        self.assertEqual(f(1), 'integer')
        self.assertEqual(f(1.0), 'floating')

    def test_overload_with_two_args(self):
        @overload
        def f(x:str, y:str) -> int: return (1, x, y)
        @overload
        def f(x:str, y:int) -> int: return (2, x, y)

        self.assertEqual(f('x', 'y'), (1, 'x', 'y'))
        self.assertEqual(f('z', 3), (2, 'z', 3))

        @overload
        def g(x:str, y:str) -> int: return 1
        @overload
        def g(x:int, y:str) -> int: return 2

        self.assertEqual(g('x', 'y'), 1)
        self.assertEqual(g('x', 1), 2)

    def test_global_overload(self):
        self.assertEqual(global_overload('x'), 's')
        self.assertEqual(global_overload(1), 'i')

    def test_partial_overload_annotation(self):
        @overload
        def f(x:str, y): return 1
        @overload
        def f(x, y:int): return 2

        self.assertEqual(f('x', object()), 1)
        self.assertEqual(f(object(), 1), 2)

    @overload
    def method_overload(self, x:str) -> str:
        return 's'

    @overload
    def method_overload(self, x:int) -> str:
        return 'i'

    def test_method_overload(self):
        self.assertEqual(self.method_overload('x'), 's')
        self.assertEqual(self.method_overload(1), 'i')

    def test_overload_with_any_type(self):
        @overload
        def f(x:Any, y:int): return 1
        @overload
        def f(x:Any, y:Any): return 2

        self.assertEqual(f((), 0), 1)
        self.assertEqual(f((), ()), 2)

    def test_overload_with_type_alias(self):
        @overload
        def f(x:List[int]): return 1
        @overload
        def f(x:Dict[int, str]): return 2
        @overload
        def f(x:Tuple[int, str]): return 3
        @overload
        def f(x): return 4

        self.assertEqual(f([]), 1)
        self.assertEqual(f({}), 2)
        self.assertEqual(f(()), 3)
        self.assertEqual(f((1, 'x')), 3)
        self.assertEqual(f(1), 4)

    def test_call_overload_with_invalid_arg_count(self):
        @overload
        def f(x:int): return 1
        @overload
        def f(x:Any): return 2

        msg1 = r'f\(\) takes exactly 1 argument \(%d given\)'
        msg2 = r'f\(\) takes exactly 1 positional argument \(%d given\)'

        with self.assertRaisesRegex(TypeError, msg1 % 0):
            f()
        with self.assertRaisesRegex(TypeError, msg2 % 2):
            f(1, 2)
        with self.assertRaisesRegex(TypeError, msg2 % 3):
            f('x', 'y', 'z')

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

        msg = r'g\(\) takes no arguments \(2 given\)'
        with self.assertRaisesRegex(TypeError, msg):
            g(1, 2)

    def test_overload_dispatch_order(self):
        class A: pass
        class B(A): pass
        class C(B): pass

        @overload
        def f(x:B): return 'B'
        @overload
        def f(x:A): return 'A'

        self.assertEqual(f(B()), 'B')
        self.assertEqual(f(A()), 'A')

        @overload
        def g(x:C): return 'C'
        @overload
        def g(x:B): return 'B'
        @overload
        def g(x:A): return 'A'

        self.assertEqual(g(C()), 'C')
        self.assertEqual(g(B()), 'B')
        self.assertEqual(g(A()), 'A')

    def test_name_of_overloaded_function(self):
        @overload
        def f(x:str): return 1
        @overload
        def f(x): return 2

        self.assertEqual(f.__name__, 'f')

    def test_overloaded_function_as_str(self):
        @overload
        def f(x:str): return 1
        @overload
        def f(x): return 2

        self.assertRegex(str(f), '^<function f at.*>$')

    def test_overload_with_default_arg_values(self):
        @overload
        def f(x:str='x'): return x + '!'
        @overload
        def f(y): return y + 1

        self.assertEqual(f(), 'x!')
        self.assertEqual(f('y'), 'y!')
        self.assertEqual(f(3), 4)

        @overload
        def g(a:int, x:str='x', y:str='z'): return 1
        @overload
        def g(a, x=1): return 2

        self.assertEqual(g(1), 1)
        self.assertEqual(g('x'), 2)
        self.assertEqual(g(1, 'XX'), 1)
        self.assertEqual(g(1, 2), 2)
        self.assertEqual(g(1, 'XX', 'YY'), 1)

        with self.assertRaises(TypeError):
            g(1, 'x', 2)

    def test_no_matching_overload(self):
        @overload
        def f(x:str): return 1
        @overload
        def f(x:int): return 2

        # Fall back to the last overload variant if no annotation matches.
        self.assertEqual(f(()), 2)

    def test_function_type_dispatch_in_overload(self):
        @overload
        def f(x:Function[[], str]): return 1
        @overload
        def f(x): return 2

        self.assertEqual(f(ord), 1)
        self.assertEqual(f(str.find), 1)
        self.assertEqual(f('x'.find), 1)
        self.assertEqual(f(str), 1)
        self.assertEqual(f(TestTyping), 1)
        self.assertEqual(f(self.test_function_type_dispatch_in_overload), 1)
        self.assertEqual(f(self.assertEqual), 1)
        self.assertEqual(f(TestTyping.assertEqual), 1)

        class A:
            def __call__(self): pass

        self.assertEqual(f(A()), 1)

        self.assertEqual(f(1), 2)
        self.assertEqual(f(object()), 2)

    def test_typevar(self):
        t = typevar('t')
        self.assertEqual(t.name, 't')
        self.assertIsNone(t.values)

    def test_typevar_values(self):
        t = typevar('t', values=(int, str))
        self.assertEqual(t.name, 't')
        self.assertEqual(t.values, (int, str))

    def test_predefined_typevars(self):
        self.assertEqual(AnyStr.name, 'AnyStr')
        self.assertEqual(AnyStr.values, (str, bytes))

    def test_typevar_in_overload(self):
        t = typevar('t')

        @overload
        def f(x:t, y:str): return 1
        @overload
        def f(x, y): return 2

        self.assertEqual(f((), 'x'), 1)
        self.assertEqual(f((), 1.1), 2)

    def test_simple_generic_class(self):
        t = typevar('t')

        class C(Generic[t]):
            pass

        self.assertIs(C[int], C)
        self.assertIsInstance(C(), C)
        self.assertIsInstance(C[int](), C)

    def test_generic_class_with_two_typeargs(self):
        t = typevar('t')
        u = typevar('u')

        class C(Generic[t, u]):
            pass

        self.assertIs(C[int, str], C)
        self.assertIsInstance(C(), C)
        self.assertIsInstance(C[int, str](), C)

    def test_abstract_generic_class(self):
        t = typevar('t')
        class C(AbstractGeneric[t]):
            pass
        class D:
            pass
        self.assertIs(C[int], C)
        self.assertNotIsInstance(D(), C)
        C.register(D)
        self.assertIsInstance(D(), C)

    def test_sequence(self):
        self.assertIs(Sequence[int], Sequence)

        self.assertIsInstance([], Sequence)
        self.assertIsInstance((), Sequence)
        self.assertIsInstance('', Sequence)
        self.assertIsInstance(b'', Sequence)
        self.assertIsInstance(range(5), Sequence)
        self.assertNotIsInstance({}, Sequence)

    def test_abstract_set(self):
        self.assertIs(AbstractSet[int], AbstractSet)

        self.assertIsInstance(set(), AbstractSet)
        self.assertIsInstance(frozenset(), AbstractSet)
        self.assertIsInstance({}.keys(), AbstractSet)
        self.assertIsInstance({}.items(), AbstractSet)
        # This is consistent with collections.Set.
        self.assertNotIsInstance({}.values(), AbstractSet)

    def test_mapping(self):
        self.assertIs(Mapping[int, str], Mapping)
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

    def test_supports_round(self):
        self.assertIsInstance(1.1, SupportsRound)
        self.assertIsInstance(1, SupportsRound)
        self.assertNotIsInstance('', SupportsRound)
        self.assertNotIsInstance((), SupportsRound)

    def test_reversible(self):
        self.assertIsInstance([], Reversible)
        self.assertIsInstance(range(1), Reversible)
        self.assertNotIsInstance((), Reversible)
        self.assertNotIsInstance('', Reversible)

    def test_simple_protocol(self):
        class P(Protocol):
            def f(self): pass

        class A:
            # Conforms to P
            def f(self): pass
            def g(self): pass

        class B:
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
        class A: pass
        self.assertTrue(issubclass(A, Protocol))

    def test_protocol_with_two_attrs(self):
        class P(Protocol):
            def __int__(self): pass
            x = 0

        class A:
            # Conforms to P; attribute values don't need to be similar
            __int__ = 0
            def x(self): pass
            def f(self): pass  # Extra method

        class B:
            # Does not conform to P
            __int__ = 0
        class C:
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

        class A:
            # Conforms to P but not PP
            def f(self): pass
        class B:
            # Conforms to P and PP
            def f(self): pass
            def g(self): pass
        class C:
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

        self.assertIsInstance('', P)
        self.assertIsInstance([], P)
        self.assertIsInstance(1, P)
        self.assertNotIsInstance({}, P)

        self.assertTrue(issubclass(str, P))
        self.assertFalse(issubclass(dict, P))

    def test_generic_protocol(self):
        t = typevar('t')
        class P(Protocol[t]):
            x = 1
        class A:
            x = 2
        self.assertIsInstance(A(), P)

    def test_indexing_in_protocol(self):
        class P(Protocol):
            def __getitem__(self): pass
        class A:
            def __getitem__(self): pass
        class B:
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
        self.assertIsInstance(range(5), Sized)
        self.assertNotIsInstance(1, Sized)

        class A:
            def __len__(self): pass

        self.assertIsInstance(A(), Sized)

    def test_iterable(self):
        self.assertIsInstance([], Iterable)
        class A:
            def __iter__(self): pass
            def g(self): pass
        self.assertIsInstance(A(), Iterable)
        self.assertNotIsInstance(1, Iterable)

    def test_iterator(self):
        self.assertIsInstance(iter(''), Iterator)
        self.assertIsInstance(iter([]), Iterator)
        self.assertIsInstance(iter({}), Iterator)
        self.assertNotIsInstance([], Iterator)

        class A:
            def __iter__(self): pass
            def __next__(self): pass
        self.assertIsInstance(A(), Iterator)

        class B:
            def __iter__(self): pass
        self.assertNotIsInstance(B(), Iterator)

        class C:
            def __next__(self): pass
        self.assertNotIsInstance(C(), Iterator)

    def test_class_inheritance_and_protocols(self):
        class A:
            def __iter__(self): pass
        class B(A):
            def __next__(self): pass
        self.assertIsInstance(B(), Iterator)
        self.assertNotIsInstance(A(), Iterator)

    def test_class_multiple_inheritance_and_protocols(self):
        class A:
            def __iter__(self): pass
        class B:
            def __next__(self): pass
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

        class A:
            x = 1
            y = 1
        class B:
            x = 1
        class C:
            y = 1

        self.assertIsInstance(A(), P3)
        self.assertNotIsInstance(B(), P3)
        self.assertNotIsInstance(C(), P3)

    def test_protocol_docstrings(self):
        class P(Protocol):
            """blah"""
            def f(self): pass
        class A:
            def f(self): pass
        self.assertIsInstance(A(), P)

    def test_forward_ref_in_annotation(self):
        A = forwardref('A')
        def f(a:A) -> A:
            return a
        self.assertEqual(A.name, 'A')
        class A: pass

    def test_string_literal_in_annotation(self):
        def f(a:'str') -> 'str':
            return a + 'x'
        def f(a:'Iterable[int]') -> 'List[int]':
            return list(a)

    def test_undefined(self):
        self.assertEqual(str(Undefined), '<typing.Undefined>')
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

    def test_simple_string_literal_in_overload(self):
        @overload
        def f(a:'str') -> str: return 's'
        @overload
        def f(a:'int') -> str: return 'i'

        self.assertEqual(f(''), 's')
        self.assertEqual(f(2), 'i')

    def test_module_ref_string_literal_in_overload(self):
        @overload
        def f(a:'Dummy'): return 1
        @overload
        def f(a): return 2

        self.assertEqual(f(Dummy()), 1)
        self.assertEqual(f(2), 2)

    def test_module_ref_string_literal_in_overload(self):
        @overload
        def f(a:'Dummy'): return 1
        @overload
        def f(a): return 2

        self.assertEqual(f(Dummy()), 1)
        self.assertEqual(f(2), 2)

    def test_local_ref_string_literal_in_overload(self):
        @overload
        def f(a:'C'): return 1
        @overload
        def f(a): return 2

        class C: pass
        self.assertEqual(f(C()), 1)
        self.assertEqual(f(2), 2)

    def test_any_string_literal_in_overload(self):
        @overload
        def f(a:'Any'): return 1
        @overload
        def f(a): return 2

        self.assertEqual(f(object()), 1)
        self.assertEqual(f(None), 1)

    def test_generic_type_string_literal_in_overload(self):
        @overload
        def f(a:'List[int]'): return 1
        @overload
        def f(a): return 2

        self.assertEqual(f([]), 1)
        self.assertEqual(f(()), 2)

    def test_tuple_type_string_literal_in_overload(self):
        @overload
        def f(a:'Tuple[int]'): return 1
        @overload
        def f(a): return 2

        self.assertEqual(f(()), 1)
        self.assertEqual(f([]), 2)

    def test_function_type_string_literal_in_overload(self):
        @overload
        def f(a:'Function[[], int]'): return 1
        @overload
        def f(a): return 2

        self.assertEqual(f(ord), 1)
        self.assertEqual(f([]), 2)

    def test_forward_ref_in_overload(self):
        A = forwardref('A')

        @overload
        def f(a:A): return 1
        @overload
        def f(a): return 2

        class A: pass

        self.assertEqual(f(A()), 1)
        self.assertEqual(f(object()), 2)

    def test_construct_class_with_abstract_method(self):
        t = typevar('t')

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

    def test_overloaded_abstract_method(self):
        class A(metaclass=ABCMeta):
            @abstractmethod
            @overload
            def f(self, x:int): pass
            @abstractmethod
            @overload
            def f(self, x): pass

        with self.assertRaises(TypeError):
            A()

        class B(metaclass=ABCMeta):
            @overload
            @abstractmethod
            def f(self, x:int) -> int: pass

            @overload
            @abstractmethod
            def f(self, x) -> None: pass

        with self.assertRaises(TypeError):
            B()

        class C(B):
            @overload
            def f(self, x:int) -> int:
                return 1

            @overload
            def f(self, x):
                return 'x'

        self.assertEqual(C().f(2), 1)
        self.assertEqual(C().f(None), 'x')

    def test_builtinclass(self):
        class A: pass
        self.assertIs(builtinclass(int), int)
        self.assertIs(builtinclass(A), A)

    def test_ducktype(self):
        class A: pass
        self.assertIs(ducktype(str)(A), A)

    def test_disjointclass(self):
        class A: pass
        self.assertIs(disjointclass(str)(A), A)
        self.assertIs(disjointclass('str')(A), A)


@overload
def global_overload(x:str) -> str:
    return 's'


@overload
def global_overload(x:int) -> str:
    return 'i'


class Dummy:
    """Dummy class defined in module scope"""


if __name__ == '__main__':
    unittest.main()
