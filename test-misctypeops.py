import alore
from unittest import Suite, assert_equal
from checker import expand_type, erase_type
from types import replace_type_vars, Instance, is_constant_type, TupleType, TypeVarDef, Callable, TypeVars


class TypeOpsSuite(Suite):
    any fx
    
    def set_up(self):
        self.fx = TypeFixture()
    
    
    # ExpandTypes
    # -----------
    
    
    def test_trivial_expand(self):
        for t in self.fx.a, self.fx.o, self.fx.t, self.fx.void, self.fx.nilt, self.tuple(self.fx.a), self.callable([], self.fx.a, self.fx.a), self.fx.dyn:
            self.assert_expand(t, [], t)
            self.assert_expand(t, [], t)
            self.assert_expand(t, [], t)
    
    def test_expand_naked_type_var(self):
        self.assert_expand(self.fx.t, [alore.pair(1, self.fx.a)], self.fx.a)
        self.assert_expand(self.fx.t, [alore.pair(2, self.fx.a)], self.fx.t)
    
    def test_expand_basic_generic_types(self):
        self.assert_expand(self.fx.gt, [alore.pair(1, self.fx.a)], self.fx.ga)
    
    # IDEA: Add test cases for
    #   tuple types
    #   callable types
    #   multiple arguments
    
    def assert_expand(self, orig, map_items, result):
        lower_bounds = {}
        
        for item in map_items:
            lower_bounds[item.left] = item.right
        
        exp = expand_type(orig, lower_bounds)
        # Remove erased tags (asterisks).
        assert_equal(str(exp).replace('*', ''), str(result))
    
    
    # ReplaceTypeVars
    # ---------------
    
    
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
    # ---------
    
    
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
    
    
    # IsConstantType
    # --------------
    
    
    def test_trivial_is_constant(self):
        for t in self.fx.a, self.fx.o, self.fx.void, self.fx.nilt, self.fx.dyn, self.fx.err:
            self.assert_is_const(t)
    
    def test_is_constant_with_type_variable(self):
        self.assert_not_is_const(self.fx.t)
        self.assert_not_is_const(self.fx.s)
    
    def test_is_constant_with_generic_type(self):
        self.assert_is_const(self.fx.ga)
        self.assert_not_is_const(self.fx.gt)
    
    def test_is_constant_with_tuple_type(self):
        self.assert_is_const(self.tuple())
        self.assert_is_const(self.tuple(self.fx.a))
        self.assert_is_const(self.tuple(self.fx.a, self.fx.ga))
        
        self.assert_not_is_const(self.tuple(self.fx.a, self.fx.t))
        self.assert_not_is_const(self.tuple(self.fx.t, self.fx.a))
        self.assert_not_is_const(self.tuple(self.fx.t, self.fx.t))
    
    def test_is_constant_with_function_type(self):
        self.assert_is_const(self.fx.callable(self.fx.void))
        self.assert_is_const(self.fx.callable(self.fx.a, self.fx.a, self.fx.a))
        
        self.assert_not_is_const(self.fx.callable(self.fx.t, self.fx.a, self.fx.a))
        self.assert_not_is_const(self.fx.callable(self.fx.a, self.fx.t, self.fx.a))
        self.assert_not_is_const(self.fx.callable(self.fx.a, self.fx.a, self.fx.t))
    
    def assert_is_const(self, t):
        assert_true(is_constant_type(t))
    
    def assert_not_is_const(self, t):
        assert_true(not is_constant_type(t))
    
    
    # Helpers
    # -------
    
    
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
