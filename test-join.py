from unittest import Suite, assert_equal
from types import NoneType, UnboundType, ErrorType, TupleType, Callable
from checker import join_types, is_subtype


class JoinSuite(Suite):
    any fx
    
    def set_up(self):
        self.fx = TypeFixture()
    
    def test_trivial_cases(self):
        for simple in self.fx.void, self.fx.a, self.fx.o, self.fx.b:
            self.assert_join(simple, simple, simple)
    
    def test_class_subtyping(self):
        self.assert_join(self.fx.a, self.fx.o, self.fx.o)
        self.assert_join(self.fx.b, self.fx.o, self.fx.o)
        self.assert_join(self.fx.a, self.fx.d, self.fx.o)
        self.assert_join(self.fx.b, self.fx.c, self.fx.a)
        self.assert_join(self.fx.b, self.fx.d, self.fx.o)
    
    def test_tuples(self):
        self.assert_join(self.tuple(), self.tuple(), self.tuple())
        self.assert_join(self.tuple(self.fx.a), self.tuple(self.fx.a), self.tuple(self.fx.a))
        self.assert_join(self.tuple(self.fx.b, self.fx.c), self.tuple(self.fx.a, self.fx.d), self.tuple(self.fx.a, self.fx.o))
        
        self.assert_join(self.tuple(self.fx.a, self.fx.a), self.fx.std_tuple, self.fx.o)
        self.assert_join(self.tuple(self.fx.a), self.tuple(self.fx.a, self.fx.a), self.fx.o)
    
    def test_function_types(self):
        self.assert_join(self.callable(self.fx.a, self.fx.b), self.callable(self.fx.a, self.fx.b), self.callable(self.fx.a, self.fx.b))
        
        self.assert_join(self.callable(self.fx.a, self.fx.b), self.callable(self.fx.b, self.fx.b), self.fx.o)
        self.assert_join(self.callable(self.fx.a, self.fx.b), self.callable(self.fx.a, self.fx.a), self.fx.o)
    
    def test_type_vars(self):
        self.assert_join(self.fx.t, self.fx.t, self.fx.t)
        self.assert_join(self.fx.s, self.fx.s, self.fx.s)
        self.assert_join(self.fx.t, self.fx.s, self.fx.o)
    
    def test_void(self):
        self.assert_join(self.fx.void, self.fx.void, self.fx.void)
        self.assert_join(self.fx.void, self.fx.dyn, self.fx.dyn)
        
        # Join of any other type against void results in ErrorType, since there
        # is no other meaningful result.
        for t in self.fx.a, self.fx.o, NoneType(), UnboundType('x'), self.fx.t, self.tuple(), self.callable(self.fx.a, self.fx.b):
            self.assert_join(t, self.fx.void, self.fx.err)
    
    def test_nil(self):
        # Any type t joined with nil results in t.
        for t in NoneType(), self.fx.a, self.fx.o, UnboundType('x'), self.fx.t, self.tuple(), self.callable(self.fx.a, self.fx.b), self.fx.dyn:
            self.assert_join(t, NoneType(), t)
    
    def test_unbound_type(self):
        self.assert_join(UnboundType('x'), UnboundType('x'), self.fx.dyn)
        self.assert_join(UnboundType('x'), UnboundType('y'), self.fx.dyn)
        
        # Any type t joined with an unbound type results in dynamic. Unbound type
        # means that there is an error somewhere in the program, so this does not
        # affect type safety (whatever the result).
        for t in self.fx.a, self.fx.o, self.fx.ga, self.fx.t, self.tuple(), self.callable(self.fx.a, self.fx.b):
            self.assert_join(t, UnboundType('X'), self.fx.dyn)
    
    def test_any_type(self):
        # Join against dynamic type always results in dynamic.
        for t in self.fx.dyn, self.fx.a, self.fx.o, NoneType(), UnboundType('x'), self.fx.void, self.fx.t, self.tuple(), self.callable(self.fx.a, self.fx.b):
            self.assert_join(t, self.fx.dyn, self.fx.dyn)
    
    def test_other_mixed_types(self):
        # In general, joining unrelated types produces object.
        for t1 in self.fx.a, self.fx.t, self.tuple(), self.callable(self.fx.a, self.fx.b):
            for t2 in self.fx.a, self.fx.t, self.tuple(), self.callable(self.fx.a, self.fx.b):
                if str(t1) != str(t2):
                    self.assert_join(t1, t2, self.fx.o)
    
    def test_error_type(self):
        self.assert_join(self.fx.err, self.fx.dyn, self.fx.dyn)
        
        # Meet against any type except dynamic results in ErrorType.
        for t in self.fx.a, self.fx.o, NoneType(), UnboundType('x'), self.fx.void, self.fx.t, self.tuple(), self.callable(self.fx.a, self.fx.b):
            self.assert_join(t, self.fx.err, self.fx.err)
    
    def test_simple_generics(self):
        self.assert_join(self.fx.ga, self.fx.ga, self.fx.ga)
        self.assert_join(self.fx.ga, self.fx.gb, self.fx.o)
        self.assert_join(self.fx.ga, self.fx.g2a, self.fx.o)
        
        self.assert_join(self.fx.ga, self.fx.nilt, self.fx.ga)
        self.assert_join(self.fx.ga, self.fx.dyn, self.fx.dyn)
        
        for t in self.fx.a, self.fx.o, self.fx.t, self.tuple(), self.callable(self.fx.a, self.fx.b):
            self.assert_join(t, self.fx.ga, self.fx.o)
    
    def test_generics_with_multiple_args(self):
        self.assert_join(self.fx.hab, self.fx.hab, self.fx.hab)
        self.assert_join(self.fx.hab, self.fx.haa, self.fx.o)
        self.assert_join(self.fx.hab, self.fx.hbb, self.fx.o)
    
    def test_generics_with_inheritance(self):
        self.assert_join(self.fx.gsab, self.fx.gb, self.fx.gb)
        self.assert_join(self.fx.gsba, self.fx.gb, self.fx.o)
    
    def test_generics_with_inheritance_and_shared_supertype(self):
        self.assert_join(self.fx.gsba, self.fx.gs2a, self.fx.ga)
        self.assert_join(self.fx.gsab, self.fx.gs2a, self.fx.o)
    
    def test_generic_types_and_any(self):
        self.assert_join(self.fx.gdyn, self.fx.ga, self.fx.gdyn)
    
    def test_callables_with_any(self):
        self.assert_join(self.callable(self.fx.a, self.fx.a, self.fx.dyn, self.fx.a), self.callable(self.fx.a, self.fx.dyn, self.fx.a, self.fx.dyn), self.callable(self.fx.a, self.fx.dyn, self.fx.dyn, self.fx.dyn))
    
    def test_join_interface_types(self):
        self.assert_join(self.fx.f, self.fx.f, self.fx.f)
        self.assert_join(self.fx.f, self.fx.f2, self.fx.o)
        self.assert_join(self.fx.f, self.fx.f3, self.fx.f)
    
    def test_join_interface_and_class_types(self):
        self.skip() # FIX
        
        self.assert_join(self.fx.o, self.fx.f, self.fx.o)
        self.assert_join(self.fx.a, self.fx.f, self.fx.o)
        
        self.assert_join(self.fx.e, self.fx.f, self.fx.f)
    
    def test_join_class_types_with_interface_result(self):
        # Unique result
        self.assert_join(self.fx.e, self.fx.e2, self.fx.f)
        
        # Ambiguous result
        self.assert_join(self.fx.e2, self.fx.e3, self.fx.err)
    
    def test_generic_interfaces(self):
        self.skip() # FIX
        
        fx = InterfaceTypeFixture()
        
        self.assert_join(fx.gfa, fx.gfa, fx.gfa)
        self.assert_join(fx.gfa, fx.gfb, fx.o)
        
        self.assert_join(fx.m1, fx.gfa, fx.gfa)
        
        self.assert_join(fx.m1, fx.gfb, fx.o)
    
    def test_simple_type_objects(self):
        t1 = self.type_callable(self.fx.a, self.fx.a)
        t2 = self.type_callable(self.fx.b, self.fx.b)
        
        self.assert_join(t1, t1, t1)
        assert_true(join_types(t1, t1, self.fx.basic).is_type_obj)
        
        self.assert_join(t1, t2, self.fx.std_type)
        self.assert_join(t1, self.fx.std_type, self.fx.std_type)
        self.assert_join(self.fx.std_type, self.fx.std_type, self.fx.std_type)
    
    # There are additional test cases in check-inference.test.
    
    # FIX interfaces with different paths
    
    # FIX generic interfaces + inheritance
    # FIX generic interfaces + ranges
    
    # FIX function types + varargs and default args
    
    def assert_join(self, s, t, join):
        self.assert_simple_join(s, t, join)
        self.assert_simple_join(t, s, join)
    
    def assert_simple_join(self, s, t, join):
        result = join_types(s, t, self.fx.basic)
        actual = str(result)
        expected = str(join)
        assert_equal(actual, expected, 'join({}, {}) == {{}} ({{}} expected)'.format(s, t))
        if not isinstance(s, ErrorType) and not isinstance(result, ErrorType):
            assert_true(is_subtype(s, result), '{} not subtype of {}'.format(s, result))
        if not isinstance(t, ErrorType) and not isinstance(result, ErrorType):
            assert_true(is_subtype(t, result), '{} not subtype of {}'.format(t, result))
    
    def tuple(self, *a):
        return TupleType(a)
    
    # callable(a1, ..., an, r) constructs a callable with argument types
    # a1, ... an and return type r.
    def callable(self, *a):
        return Callable(a[:-1], len(a) - 1, False, a[-1], False)
    
    # typeCallable(a1, ..., an, r) constructs a callable with argument types
    # a1, ... an and return type r, and which represents a type.
    def type_callable(self, *a):
        return Callable(a[:-1], len(a) - 1, False, a[-1], True)
