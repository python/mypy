"""Test cases for type inference helper functions."""

import typing

from mypy.myunit import Suite, assert_equal, assert_true
from mypy.checkexpr import map_actuals_to_formals
from mypy.nodes import ARG_POS, ARG_OPT, ARG_STAR, ARG_STAR2, ARG_NAMED
from mypy.types import AnyType, TupleType


class MapActualsToFormalsSuite(Suite):
    """Test cases for checkexpr.map_actuals_to_formals."""

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
            self.tuple(AnyType()))
        self.assert_vararg_map(
            [ARG_STAR],
            [ARG_POS, ARG_POS],
            [[0], [0]],
            self.tuple(AnyType(), AnyType()))
        self.assert_vararg_map(
            [ARG_STAR],
            [ARG_POS, ARG_OPT, ARG_OPT],
            [[0], [0], []],
            self.tuple(AnyType(), AnyType()))

    def tuple(self, *args):
        return TupleType(args, None)

    def test_named_args(self):
        self.assert_map(
            ['x'],
            [(ARG_POS, 'x')],
            [[0]])
        self.assert_map(
            ['y', 'x'],
            [(ARG_POS, 'x'), (ARG_POS, 'y')],
            [[1], [0]])

    def test_some_named_args(self):
        self.assert_map(
            ['y'],
            [(ARG_OPT, 'x'), (ARG_OPT, 'y'), (ARG_OPT, 'z')],
            [[], [0], []])

    def test_missing_named_arg(self):
        self.assert_map(
            ['y'],
            [(ARG_OPT, 'x')],
            [[]])

    def test_duplicate_named_arg(self):
        self.assert_map(
            ['x', 'x'],
            [(ARG_OPT, 'x')],
            [[0, 1]])

    def test_varargs_and_bare_asterisk(self):
        self.assert_map(
            [ARG_STAR],
            [ARG_STAR, (ARG_NAMED, 'x')],
            [[0], []])
        self.assert_map(
            [ARG_STAR, 'x'],
            [ARG_STAR, (ARG_NAMED, 'x')],
            [[0], [1]])

    def test_keyword_varargs(self):
        self.assert_map(
            ['x'],
            [ARG_STAR2],
            [[0]])
        self.assert_map(
            ['x', ARG_STAR2],
            [ARG_STAR2],
            [[0, 1]])
        self.assert_map(
            ['x', ARG_STAR2],
            [(ARG_POS, 'x'), ARG_STAR2],
            [[0], [1]])
        self.assert_map(
            [ARG_POS, ARG_STAR2],
            [(ARG_POS, 'x'), ARG_STAR2],
            [[0], [1]])

    def test_both_kinds_of_varargs(self):
        self.assert_map(
            [ARG_STAR, ARG_STAR2],
            [(ARG_POS, 'x'), (ARG_POS, 'y')],
            [[0, 1], [0, 1]])

    def test_special_cases(self):
        self.assert_map([ARG_STAR],
                        [ARG_STAR, ARG_STAR2],
                        [[0], []])
        self.assert_map([ARG_STAR, ARG_STAR2],
                        [ARG_STAR, ARG_STAR2],
                        [[0], [1]])
        self.assert_map([ARG_STAR2],
                        [(ARG_POS, 'x'), ARG_STAR2],
                        [[0], [0]])
        self.assert_map([ARG_STAR2],
                        [ARG_STAR2],
                        [[0]])

    def assert_map(self, caller_kinds, callee_kinds, expected):
        caller_kinds, caller_names = expand_caller_kinds(caller_kinds)
        callee_kinds, callee_names = expand_callee_kinds(callee_kinds)
        result = map_actuals_to_formals(
            caller_kinds,
            caller_names,
            callee_kinds,
            callee_names,
            lambda i: AnyType())
        assert_equal(result, expected)

    def assert_vararg_map(self, caller_kinds, callee_kinds, expected,
                          vararg_type):
        result = map_actuals_to_formals(
            caller_kinds,
            [],
            callee_kinds,
            [],
            lambda i: vararg_type)
        assert_equal(result, expected)


def expand_caller_kinds(kinds_or_names):
    kinds = []
    names = []
    for k in kinds_or_names:
        if isinstance(k, str):
            kinds.append(ARG_NAMED)
            names.append(k)
        else:
            kinds.append(k)
            names.append(None)
    return kinds, names


def expand_callee_kinds(kinds_and_names):
    kinds = []
    names = []
    for v in kinds_and_names:
        if isinstance(v, tuple):
            kinds.append(v[0])
            names.append(v[1])
        else:
            kinds.append(v)
            names.append(None)
    return kinds, names
