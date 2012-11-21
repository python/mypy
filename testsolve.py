from myunit import Suite, assert_equal
from constraints import SUPERTYPE_OF, SUBTYPE_OF, Constraint
from solve import solve_constraints
from typefixture import TypeFixture


class SolveSuite(Suite):
    def __init__(self):
        super().__init__()
        self.fx = TypeFixture()
    
    def test_empty_input(self):
        self.assert_solve([], [], [])
    
    def test_simple_supertype_constraints(self):
        self.assert_solve(['T'],
                          [self.supc(self.fx.t, self.fx.a)],
                          [(self.fx.a, self.fx.o)])
        self.assert_solve(['T'],
                          [self.supc(self.fx.t, self.fx.a),
                           self.supc(self.fx.t, self.fx.b)],
                          [(self.fx.a, self.fx.o)])
    
    def test_simple_subtype_constraints(self):
        self.assert_solve(['T'],
                          [self.subc(self.fx.t, self.fx.a)],
                          [(self.fx.nilt, self.fx.a)])
        self.assert_solve(['T'],
                          [self.subc(self.fx.t, self.fx.a),
                           self.subc(self.fx.t, self.fx.b)],
                          [(self.fx.nilt, self.fx.b)])
    
    def test_both_kinds_of_constraints(self):
        self.assert_solve(['T'],
                          [self.supc(self.fx.t, self.fx.b),
                           self.subc(self.fx.t, self.fx.a)],
                          [(self.fx.b, self.fx.a)])
    
    def test_unsatisfiable_constraints(self):
        # The constraints are impossible to satisfy.
        self.assert_solve(['T'],
                          [self.supc(self.fx.t, self.fx.a),
                           self.subc(self.fx.t, self.fx.b)],
                          [None])
    
    def test_exactly_specified_result(self):
        self.assert_solve(['T'],
                          [self.supc(self.fx.t, self.fx.b),
                           self.subc(self.fx.t, self.fx.b)],
                          [(self.fx.b, self.fx.b)])
    
    def test_multiple_variables(self):
        self.assert_solve(['T', 'S'],
                          [self.supc(self.fx.t, self.fx.b),
                           self.supc(self.fx.s, self.fx.c),
                           self.subc(self.fx.t, self.fx.a)],
                          [(self.fx.b, self.fx.a), (self.fx.c, self.fx.o)])
    
    def test_no_constraints_for_var(self):
        self.assert_solve(['T'],
                          [],
                          [(self.fx.nilt, self.fx.o)])
        self.assert_solve(['T', 'S'],
                          [],
                          [(self.fx.nilt, self.fx.o),
                           (self.fx.nilt, self.fx.o)])
        self.assert_solve(['T', 'S'],
                          [self.supc(self.fx.s, self.fx.a)],
                          [(self.fx.nilt, self.fx.o), (self.fx.a, self.fx.o)])
    
    def test_void_constraints(self):
        self.assert_solve(['T'],
                          [self.supc(self.fx.t, self.fx.void)],
                          [(self.fx.void, self.fx.void)])
        self.assert_solve(['T'],
                          [self.subc(self.fx.t, self.fx.void)],
                          [(self.fx.void, self.fx.void)])
        
        # Both bounds void.
        self.assert_solve(['T'],
                          [self.supc(self.fx.t, self.fx.void),
                           self.subc(self.fx.t, self.fx.void)],
                          [(self.fx.void, self.fx.void)])
        
        # Cannot infer any type.
        self.assert_solve(['T'],
                          [self.supc(self.fx.t, self.fx.a),
                           self.supc(self.fx.t, self.fx.void)],
                          [None])
        self.assert_solve(['T'],
                          [self.subc(self.fx.t, self.fx.a),
                           self.subc(self.fx.t, self.fx.void)],
                          [None])
    
    def test_simple_constraints_with_dynamic_type(self):
        self.assert_solve(['T'],
                          [self.supc(self.fx.t, self.fx.dyn)],
                          [(self.fx.dyn, self.fx.dyn)])
        self.assert_solve(['T'],
                          [self.supc(self.fx.t, self.fx.dyn),
                           self.supc(self.fx.t, self.fx.dyn)],
                          [(self.fx.dyn, self.fx.dyn)])
        self.assert_solve(['T'],
                          [self.supc(self.fx.t, self.fx.dyn),
                           self.supc(self.fx.t, self.fx.a)],
                          [(self.fx.dyn, self.fx.dyn)])
        
        self.assert_solve(['T'],
                          [self.subc(self.fx.t, self.fx.dyn)],
                          [(self.fx.dyn, self.fx.dyn)])
        self.assert_solve(['T'],
                          [self.subc(self.fx.t, self.fx.dyn),
                           self.subc(self.fx.t, self.fx.dyn)],
                          [(self.fx.dyn, self.fx.dyn)])
        self.assert_solve(['T'],
                          [self.subc(self.fx.t, self.fx.dyn),
                           self.subc(self.fx.t, self.fx.a)],
                          [(self.fx.dyn, self.fx.dyn)])
    
    def test_both_normal_and_dynamic_types_in_results(self):
        # If one of the bounds is dynamic, we promote the other bound to
        # dynamic as well, since otherwise the type range does not make sense.
        self.assert_solve(['T'],
                          [self.supc(self.fx.t, self.fx.a),
                           self.subc(self.fx.t, self.fx.dyn)],
                          [(self.fx.dyn, self.fx.dyn)])
        
        self.assert_solve(['T'],
                          [self.supc(self.fx.t, self.fx.dyn),
                           self.subc(self.fx.t, self.fx.a)],
                          [(self.fx.dyn, self.fx.dyn)])
    
    def assert_solve(self, vars, constraints, results):
        res = []
        for r in results:
            if isinstance(r, tuple):
                res.append(r[0])
            else:
                res.append(r)
        actual = solve_constraints(vars, constraints, self.fx.basic)
        assert_equal(str(actual), str(res))
    
    def supc(self, type_var, bound):
        return Constraint(type_var.name, SUPERTYPE_OF, bound)
    
    def subc(self, type_var, bound):
        return Constraint(type_var.name, SUBTYPE_OF, bound)
