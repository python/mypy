from unittest import Suite, assert_equal
from types import UnboundType, Any, Void, Callable, TupleType, TypeVarDef, TypeVars


class TypesSuite(Suite):
    # Helper constants
    x = UnboundType('X')
    y = UnboundType('Y')
    
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
        c = Callable([self.x, self.y], 2, False, self.y, False, None, TypeVars([TypeVarDef('X', -1)]))
        assert_equal(str(c), 'def <X> (X?, Y?) -> Y?')
        
        v = TypeVars([TypeVarDef('Y', -1, UnboundType('X')), TypeVarDef('X', -2)])
        c2 = Callable([], 0, False, Void(None), False, None, v)
        assert_equal(str(c2), 'def <Y is X?, X> ()')
