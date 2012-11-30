"""Test cases for type inference helper functions."""

import sys

from myunit import Suite, assert_equal, assert_true, run_test
from checkexpr import map_actuals_to_formals
from nodes import ARG_POS, ARG_OPT, ARG_STAR
from mtypes import Any, TupleType


class MapActualsToFormalsSuite(Suite):
    def test_basic(self):
        self.assert_map([], [], [])

    def test_positional_only(self):
        self.assert_map([ARG_POS],
                        [ARG_POS],
                        [[0]])
        self.assert_map([ARG_POS, ARG_POS],
                        [ARG_POS, ARG_POS],
                        [[0], [1]])

    def test_optional(self):
        self.assert_map([],
                        [ARG_OPT],
                        [[]])
        self.assert_map([ARG_POS],
                        [ARG_OPT],
                        [[0]])
        self.assert_map([ARG_POS],
                        [ARG_OPT, ARG_OPT],
                        [[0], []])

    def test_callee_star(self):
        self.assert_map([],
                        [ARG_STAR],
                        [[]])
        self.assert_map([ARG_POS],
                        [ARG_STAR],
                        [[0]])
        self.assert_map([ARG_POS, ARG_POS],
                        [ARG_STAR],
                        [[0, 1]])

    def test_caller_star(self):
        self.assert_map([ARG_STAR],
                        [ARG_STAR],
                        [[0]])
        self.assert_map([ARG_POS, ARG_STAR],
                        [ARG_STAR],
                        [[0, 1]])
        self.assert_map([ARG_STAR],
                        [ARG_POS, ARG_STAR],
                        [[0], [0]])
        self.assert_map([ARG_STAR],
                        [ARG_OPT, ARG_STAR],
                        [[0], [0]])

    def test_too_many_caller_args(self):
        self.assert_map([ARG_POS],
                        [],
                        [])
        self.assert_map([ARG_STAR],
                        [],
                        [])
        self.assert_map([ARG_STAR],
                        [ARG_POS],
                        [[0]])

    def test_tuple_star(self):
        self.assert_vararg_map(
            [ARG_STAR],
            [ARG_POS],
            [[0]],
            TupleType([Any()]))
        self.assert_vararg_map(
            [ARG_STAR],
            [ARG_POS, ARG_POS],
            [[0], [0]],
            TupleType([Any(), Any()]))
        self.assert_vararg_map(
            [ARG_STAR],
            [ARG_POS, ARG_OPT, ARG_OPT],
            [[0], [0], []],
            TupleType([Any(), Any()]))

    def assert_map(self, caller_kinds, callee_kinds, expected):
        result = map_actuals_to_formals(
            caller_kinds, callee_kinds, lambda i: Any())
        assert_equal(result, expected)

    def assert_vararg_map(self, caller_kinds, callee_kinds, expected,
                           vararg_type):
        result = map_actuals_to_formals(
            caller_kinds, callee_kinds, lambda i: vararg_type)
        assert_equal(result, expected)


if __name__ == '__main__':
    run_test(MapActualsToFormalsSuite(), sys.argv[1:])
