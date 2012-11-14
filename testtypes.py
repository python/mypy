from unittest import Suite, assert_equal, assert_true
from erasetype import erase_type
from expandtype import expand_type
from mtypes import (
    UnboundType, Any, Void, Callable, TupleType, TypeVarDef, TypeVars, Typ,
    Instance
)
from replacetvars import replace_type_vars
from typefixture import TypeFixture


class TypesSuite(Suite):
    def __init__(self):
        super().__init__()
        self.x = UnboundType('X')  # Helpers
        self.y = UnboundType('Y')
    
    def test_any(self):
        assert_equal(str(Any()), 'any')
    
    def test_simple_unbound_type(self):
        u = UnboundType('Foo')
        assert_equal(str(u), 'Foo?')
    
    def test_generic_unbound_type(self):
        u = UnboundType('Foo', [UnboundType('T'), Any()])
        assert_equal(str(u), 'Foo?<T?, any>')
    
    def test_void_type(self):
        assert_equal(str(Void(None)), 'void')
    
    def test_callable_type(self):
        c = Callable([self.x, self.y], 2, False, Any(), False)
        assert_equal(str(c), 'def (X?, Y?) -> any')
        
        c2 = Callable([], 0, False, Void(None), False)
        assert_equal(str(c2), 'def ()')
    
    def test_callable_type_with_default_args(self):
        c = Callable([self.x, self.y], 1, False, Any(), False)
        assert_equal(str(c), 'def (X?, Y?=) -> any')
        
        c2 = Callable([self.x, self.y], 0, False, Any(), False)
        assert_equal(str(c2), 'def (X?=, Y?=) -> any')
    
    def test_callable_type_with_var_args(self):
        c = Callable([self.x], 0, True, Any(), False)
        assert_equal(str(c), 'def (*X?) -> any')
        
        c2 = Callable([self.x, self.y], 1, True, Any(), False)
        assert_equal(str(c2), 'def (X?, *Y?) -> any')
        
        c3 = Callable([self.x, self.y], 0, True, Any(), False)
        assert_equal(str(c3), 'def (X?=, *Y?) -> any')
    
    def test_tuple_type(self):
        assert_equal(str(TupleType([])), 'tuple<>')
        assert_equal(str(TupleType([self.x])), 'tuple<X?>')
        assert_equal(str(TupleType([self.x, Any()])), 'tuple<X?, any>')
    
    def test_type_variable_binding(self):
        assert_equal(str(TypeVarDef('X', 1)), 'X')
        assert_equal(str(TypeVarDef('X', 1, UnboundType('Y'))), 'X is Y?')
    
    def test_generic_function_type(self):
        c = Callable([self.x, self.y], 2, False, self.y, False, None,
                     TypeVars([TypeVarDef('X', -1)]))
        assert_equal(str(c), 'def <X> (X?, Y?) -> Y?')
        
        v = TypeVars([TypeVarDef('Y', -1, UnboundType('X')),
                      TypeVarDef('X', -2)])
        c2 = Callable([], 0, False, Void(None), False, None, v)
        assert_equal(str(c2), 'def <Y is X?, X> ()')


class TypeOpsSuite(Suite):
    def set_up(self):
        self.fx = TypeFixture()
    
    # ExpandTypes
    
    def test_trivial_expand(self):
        for t in self.fx.a, self.fx.o, self.fx.t, self.fx.void, self.fx.nilt, self.tuple(self.fx.a), self.callable([], self.fx.a, self.fx.a), self.fx.dyn:
            self.assert_expand(t, [], t)
            self.assert_expand(t, [], t)
            self.assert_expand(t, [], t)
    
    def test_expand_naked_type_var(self):
        self.assert_expand(self.fx.t, [(1, self.fx.a)], self.fx.a)
        self.assert_expand(self.fx.t, [(2, self.fx.a)], self.fx.t)
    
    def test_expand_basic_generic_types(self):
        self.assert_expand(self.fx.gt, [(1, self.fx.a)], self.fx.ga)
    
    # IDEA: Add test cases for
    #   tuple types
    #   callable types
    #   multiple arguments
    
    def assert_expand(self, orig, map_items, result):
        lower_bounds = {}
        
        for id, t in map_items:
            lower_bounds[id] = t
        
        exp = expand_type(orig, lower_bounds)
        # Remove erased tags (asterisks).
        assert_equal(str(exp).replace('*', ''), str(result))
    
    # ReplaceTypeVars
    
    def test_trivial_replace(self):
        for t in self.fx.a, self.fx.o, self.fx.void, self.fx.nilt, self.tuple(self.fx.a), self.callable([], self.fx.a, self.fx.a), self.fx.dyn, self.fx.err:
            self.assert_replace(t, t)
    
    def test_replace_type_var(self):
        self.assert_replace(self.fx.t, self.fx.dyn)
    
    def test_replace_generic_instance(self):
        self.assert_replace(self.fx.ga, self.fx.ga)
        self.assert_replace(self.fx.gt, self.fx.gdyn)
    
    def assert_replace(self, orig, result):
        assert_equal(str(replace_type_vars(orig)), str(result))
    
    # EraseType
    
    def test_trivial_erase(self):
        for t in self.fx.a, self.fx.o, self.fx.void, self.fx.nilt, self.fx.dyn, self.fx.err:
            self.assert_erase(t, t)
    
    def test_erase_with_type_variable(self):
        self.assert_erase(self.fx.t, self.fx.dyn)
    
    def test_erase_with_generic_type(self):
        self.assert_erase(self.fx.ga, self.fx.gdyn)
        self.assert_erase(self.fx.hab, Instance(self.fx.hi, [self.fx.dyn, self.fx.dyn]))
    
    def test_erase_with_tuple_type(self):
        self.assert_erase(self.tuple(self.fx.a), self.fx.std_tuple)
    
    def test_erase_with_function_type(self):
        self.assert_erase(self.fx.callable(self.fx.a, self.fx.b), self.fx.std_function)
    
    def test_erase_with_type_object(self):
        self.assert_erase(self.fx.callable_type(self.fx.a, self.fx.b), self.fx.std_function)
    
    def assert_erase(self, orig, result):
        assert_equal(str(erase_type(orig, self.fx.basic)), str(result))
    
    # Helpers
    
    def tuple(self, *a):
        return TupleType(a)
    
    # callable(args, a1, ..., an, r) constructs a callable with argument types
    # a1, ... an and return type r and type arguments vars.
    def callable(self, vars, *a):
        tv = []
        n = -1
        for v in vars:
            tv.append(TypeVarDef(v, n))
            n -= 1
        return Callable(a[:-1], len(a) - 1, False, a[-1], False, None, TypeVars(tv))
