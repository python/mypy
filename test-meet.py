from unittest import Suite, assert_equal
from types import NoneType, UnboundType, ErrorType, TupleType, Callable
from checker import meet_types, is_subtype


class MeetSuite(Suite):
    any fx
    
    def set_up(self):
        self.fx = TypeFixture()
    
    def test_trivial_cases(self):
        for simple in self.fx.void, self.fx.a, self.fx.o, self.fx.b:
            self.assert_meet(simple, simple, simple)
    
    def test_class_subtyping(self):
        self.assert_meet(self.fx.a, self.fx.o, self.fx.a)
        self.assert_meet(self.fx.a, self.fx.b, self.fx.b)
        self.assert_meet(self.fx.b, self.fx.o, self.fx.b)
        self.assert_meet(self.fx.a, self.fx.d, NoneType())
        self.assert_meet(self.fx.b, self.fx.c, NoneType())
    
    def test_tuples(self):
        self.assert_meet(self.tuple(), self.tuple(), self.tuple())
        self.assert_meet(self.tuple(self.fx.a), self.tuple(self.fx.a), self.tuple(self.fx.a))
        self.assert_meet(self.tuple(self.fx.b, self.fx.c), self.tuple(self.fx.a, self.fx.d), self.tuple(self.fx.b, NoneType()))
        
        self.assert_meet(self.tuple(self.fx.a, self.fx.a), self.fx.std_tuple, NoneType())
        self.assert_meet(self.tuple(self.fx.a), self.tuple(self.fx.a, self.fx.a), NoneType())
    
    def test_function_types(self):
        self.assert_meet(self.callable(self.fx.a, self.fx.b), self.callable(self.fx.a, self.fx.b), self.callable(self.fx.a, self.fx.b))
        
        self.assert_meet(self.callable(self.fx.a, self.fx.b), self.callable(self.fx.b, self.fx.b), NoneType())
        self.assert_meet(self.callable(self.fx.a, self.fx.b), self.callable(self.fx.a, self.fx.a), NoneType())
    
    def test_type_vars(self):
        self.assert_meet(self.fx.t, self.fx.t, self.fx.t)
        self.assert_meet(self.fx.s, self.fx.s, self.fx.s)
        self.assert_meet(self.fx.t, self.fx.s, NoneType())
    
    def test_void(self):
        self.assert_meet(self.fx.void, self.fx.void, self.fx.void)
        self.assert_meet(self.fx.void, self.fx.dyn, self.fx.dyn)
        
        # Meet of any other type against void results in ErrorType, since there
        # is no meaningful valid result.
        for t in self.fx.a, self.fx.o, UnboundType('x'), NoneType(), self.fx.t, self.tuple(), self.callable(self.fx.a, self.fx.b):
            self.assert_meet(t, self.fx.void, self.fx.err)
    
    def test_nil(self):
        self.assert_meet(NoneType(), NoneType(), NoneType())
        
        self.assert_meet(NoneType(), self.fx.dyn, self.fx.dyn)
        self.assert_meet(NoneType(), self.fx.void, self.fx.err)
        
        # Any type t joined with nil results in nil, unless t is dynamic or void.
        for t in self.fx.a, self.fx.o, UnboundType('x'), self.fx.t, self.tuple(), self.callable(self.fx.a, self.fx.b):
            self.assert_meet(t, NoneType(), NoneType())
    
    def test_unbound_type(self):
        self.assert_meet(UnboundType('x'), UnboundType('x'), self.fx.dyn)
        self.assert_meet(UnboundType('x'), UnboundType('y'), self.fx.dyn)
        
        self.assert_meet(UnboundType('x'), self.fx.void, self.fx.err)
        
        # The meet of any type t with an unbound type results in dynamic (except
        # for void). Unbound type means that there is an error somewhere in the
        # program, so this does not affect type safety.
        for t in self.fx.dyn, self.fx.a, self.fx.o, self.fx.t, self.tuple(), self.callable(self.fx.a, self.fx.b):
            self.assert_meet(t, UnboundType('X'), self.fx.dyn)
    
    def test_dynamic_type(self):
        # Meet against dynamic type always results in dynamic.
        for t in self.fx.dyn, self.fx.a, self.fx.o, NoneType(), UnboundType('x'), self.fx.void, self.fx.t, self.tuple(), self.callable(self.fx.a, self.fx.b):
            self.assert_meet(t, self.fx.dyn, self.fx.dyn)
    
    def test_error_type(self):
        self.assert_meet(self.fx.err, self.fx.dyn, self.fx.dyn)
        
        # Meet against any type except dynamic results in ErrorType.
        for t in self.fx.a, self.fx.o, NoneType(), UnboundType('x'), self.fx.void, self.fx.t, self.tuple(), self.callable(self.fx.a, self.fx.b):
            self.assert_meet(t, self.fx.err, self.fx.err)
    
    def test_simple_generics(self):
        self.assert_meet(self.fx.ga, self.fx.ga, self.fx.ga)
        self.assert_meet(self.fx.ga, self.fx.o, self.fx.ga)
        self.assert_meet(self.fx.ga, self.fx.gb, self.fx.nilt)
        self.assert_meet(self.fx.ga, self.fx.g2a, self.fx.nilt)
        
        self.assert_meet(self.fx.ga, self.fx.nilt, self.fx.nilt)
        self.assert_meet(self.fx.ga, self.fx.dyn, self.fx.dyn)
        
        for t in self.fx.a, self.fx.t, self.tuple(), self.callable(self.fx.a, self.fx.b):
            self.assert_meet(t, self.fx.ga, self.fx.nilt)
    
    def test_generics_with_multiple_args(self):
        self.assert_meet(self.fx.hab, self.fx.hab, self.fx.hab)
        self.assert_meet(self.fx.hab, self.fx.haa, self.fx.nilt)
        self.assert_meet(self.fx.hab, self.fx.hbb, self.fx.nilt)
    
    def test_generics_with_inheritance(self):
        self.assert_meet(self.fx.gsab, self.fx.gb, self.fx.gsab)
        self.assert_meet(self.fx.gsba, self.fx.gb, self.fx.nilt)
    
    def test_generics_with_inheritance_and_shared_supertype(self):
        self.assert_meet(self.fx.gsba, self.fx.gs2a, self.fx.nilt)
        self.assert_meet(self.fx.gsab, self.fx.gs2a, self.fx.nilt)
    
    def test_generic_types_and_dynamic(self):
        self.assert_meet(self.fx.gdyn, self.fx.ga, self.fx.gdyn)
    
    def test_callables_with_dynamic(self):
        self.assert_meet(self.callable(self.fx.a, self.fx.a, self.fx.dyn, self.fx.a), self.callable(self.fx.a, self.fx.dyn, self.fx.a, self.fx.dyn), self.callable(self.fx.a, self.fx.dyn, self.fx.dyn, self.fx.dyn))
    
    def test_meet_interface_types(self):
        self.assert_meet(self.fx.f, self.fx.f, self.fx.f)
        self.assert_meet(self.fx.f, self.fx.f2, self.fx.nilt)
        self.assert_meet(self.fx.f, self.fx.f3, self.fx.f3)
    
    def test_join_interface_and_class_types(self):
        self.assert_meet(self.fx.o, self.fx.f, self.fx.f)
        self.assert_meet(self.fx.a, self.fx.f, self.fx.nilt)
        
        self.assert_meet(self.fx.e, self.fx.f, self.fx.e)
    
    def test_join_class_types_with_shared_interfaces(self):
        # These have nothing special with respect to meets, unlike joins. These
        # are for completeness only.
        self.assert_meet(self.fx.e, self.fx.e2, self.fx.nilt)
        self.assert_meet(self.fx.e2, self.fx.e3, self.fx.nilt)
    
    def test_meet_with_generic_interfaces(self):
        # TODO fix
        self.skip()
        
        fx = InterfaceTypeFixture()
        self.assert_meet(fx.gfa, fx.m1, fx.m1)
        self.assert_meet(fx.gfa, fx.gfa, fx.gfa)
        self.assert_meet(fx.gfb, fx.m1, fx.nilt)
    
    # FIX generic interfaces + ranges
    
    def assert_meet(self, s, t, meet):
        self.assert_simple_meet(s, t, meet)
        self.assert_simple_meet(t, s, meet)
    
    def assert_simple_meet(self, s, t, meet):
        result = meet_types(s, t, self.fx.basic)
        actual = str(result)
        expected = str(meet)
        assert_equal(actual, expected, 'meet({}, {}) == {{}} ({{}} expected)'.format(s, t))
        if not isinstance(s, ErrorType) and not isinstance(result, ErrorType):
            assert_true(is_subtype(result, s), '{} not subtype of {}'.format(result, s))
        if not isinstance(t, ErrorType) and not isinstance(result, ErrorType):
            assert_true(is_subtype(result, t), '{} not subtype of {}'.format(result, t))
    
    def tuple(self, *a):
        return TupleType(a)
    
    # callable(a1, ..., an, r) constructs a callable with argument types
    # a1, ... an and return type r.
    def callable(self, *a):
        return Callable(a[:-1], len(a) - 1, False, a[-1], False)
