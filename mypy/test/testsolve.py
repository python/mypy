"""Test cases for the constraint solver used in type inference."""

import typing

from mypy.myunit import Suite, assert_equal
from mypy.constraints import SUPERTYPE_OF, SUBTYPE_OF, Constraint
from mypy.solve import solve_constraints
from mypy.typefixture import TypeFixture


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
                          [self.fx.a])
        self.assert_solve(['T'],
                          [self.subc(self.fx.t, self.fx.a),
                           self.subc(self.fx.t, self.fx.b)],
                          [self.fx.b])

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
                          [self.fx.nonet])
        self.assert_solve(['T', 'S'],
                          [],
                          [self.fx.nonet, self.fx.nonet])
        self.assert_solve(['T', 'S'],
                          [self.supc(self.fx.s, self.fx.a)],
                          [self.fx.nonet, (self.fx.a, self.fx.o)])

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
                          [self.supc(self.fx.t, self.fx.anyt)],
                          [(self.fx.anyt, self.fx.anyt)])
        self.assert_solve(['T'],
                          [self.supc(self.fx.t, self.fx.anyt),
                           self.supc(self.fx.t, self.fx.anyt)],
                          [(self.fx.anyt, self.fx.anyt)])
        self.assert_solve(['T'],
                          [self.supc(self.fx.t, self.fx.anyt),
                           self.supc(self.fx.t, self.fx.a)],
                          [(self.fx.anyt, self.fx.anyt)])

        self.assert_solve(['T'],
                          [self.subc(self.fx.t, self.fx.anyt)],
                          [(self.fx.anyt, self.fx.anyt)])
        self.assert_solve(['T'],
                          [self.subc(self.fx.t, self.fx.anyt),
                           self.subc(self.fx.t, self.fx.anyt)],
                          [(self.fx.anyt, self.fx.anyt)])
        # self.assert_solve(['T'],
        #                   [self.subc(self.fx.t, self.fx.anyt),
        #                    self.subc(self.fx.t, self.fx.a)],
        #                   [(self.fx.anyt, self.fx.anyt)])
        # TODO: figure out what this should be after changes to meet(any, X)

    def test_both_normal_and_any_types_in_results(self):
        # If one of the bounds is any, we promote the other bound to
        # any as well, since otherwise the type range does not make sense.
        self.assert_solve(['T'],
                          [self.supc(self.fx.t, self.fx.a),
                           self.subc(self.fx.t, self.fx.anyt)],
                          [(self.fx.anyt, self.fx.anyt)])

        self.assert_solve(['T'],
                          [self.supc(self.fx.t, self.fx.anyt),
                           self.subc(self.fx.t, self.fx.a)],
                          [(self.fx.anyt, self.fx.anyt)])

    def assert_solve(self, vars, constraints, results):
        res = []
        for r in results:
            if isinstance(r, tuple):
                res.append(r[0])
            else:
                res.append(r)
        actual = solve_constraints(vars, constraints)
        assert_equal(str(actual), str(res))

    def supc(self, type_var, bound):
        return Constraint(type_var.name, SUPERTYPE_OF, bound)

    def subc(self, type_var, bound):
        return Constraint(type_var.name, SUBTYPE_OF, bound)
