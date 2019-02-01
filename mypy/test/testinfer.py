"""Test cases for type inference helper functions."""

from typing import List, Optional, Tuple, Union

from mypy.test.helpers import Suite, assert_equal
from mypy.argmap import map_actuals_to_formals
from mypy.nodes import ARG_POS, ARG_OPT, ARG_STAR, ARG_STAR2, ARG_NAMED
from mypy.types import AnyType, TupleType, Type, TypeOfAny
from mypy.test.typefixture import TypeFixture


class MapActualsToFormalsSuite(Suite):
    """Test cases for checkexpr.map_actuals_to_formals."""

    def test_basic(self) -> None:
        self.assert_map([], [], [])

    def test_positional_only(self) -> None:
        self.assert_map([ARG_POS],
                        [ARG_POS],
                        [[0]])
        self.assert_map([ARG_POS, ARG_POS],
                        [ARG_POS, ARG_POS],
                        [[0], [1]])

    def test_optional(self) -> None:
        self.assert_map([],
                        [ARG_OPT],
                        [[]])
        self.assert_map([ARG_POS],
                        [ARG_OPT],
                        [[0]])
        self.assert_map([ARG_POS],
                        [ARG_OPT, ARG_OPT],
                        [[0], []])

    def test_callee_star(self) -> None:
        self.assert_map([],
                        [ARG_STAR],
                        [[]])
        self.assert_map([ARG_POS],
                        [ARG_STAR],
                        [[0]])
        self.assert_map([ARG_POS, ARG_POS],
                        [ARG_STAR],
                        [[0, 1]])

    def test_caller_star(self) -> None:
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

    def test_too_many_caller_args(self) -> None:
        self.assert_map([ARG_POS],
                        [],
                        [])
        self.assert_map([ARG_STAR],
                        [],
                        [])
        self.assert_map([ARG_STAR],
                        [ARG_POS],
                        [[0]])

    def test_tuple_star(self) -> None:
        any_type = AnyType(TypeOfAny.special_form)
        self.assert_vararg_map(
            [ARG_STAR],
            [ARG_POS],
            [[0]],
            self.tuple(any_type))
        self.assert_vararg_map(
            [ARG_STAR],
            [ARG_POS, ARG_POS],
            [[0], [0]],
            self.tuple(any_type, any_type))
        self.assert_vararg_map(
            [ARG_STAR],
            [ARG_POS, ARG_OPT, ARG_OPT],
            [[0], [0], []],
            self.tuple(any_type, any_type))

    def tuple(self, *args: Type) -> TupleType:
        return TupleType(list(args), TypeFixture().std_tuple)

    def test_named_args(self) -> None:
        self.assert_map(
            ['x'],
            [(ARG_POS, 'x')],
            [[0]])
        self.assert_map(
            ['y', 'x'],
            [(ARG_POS, 'x'), (ARG_POS, 'y')],
            [[1], [0]])

    def test_some_named_args(self) -> None:
        self.assert_map(
            ['y'],
            [(ARG_OPT, 'x'), (ARG_OPT, 'y'), (ARG_OPT, 'z')],
            [[], [0], []])

    def test_missing_named_arg(self) -> None:
        self.assert_map(
            ['y'],
            [(ARG_OPT, 'x')],
            [[]])

    def test_duplicate_named_arg(self) -> None:
        self.assert_map(
            ['x', 'x'],
            [(ARG_OPT, 'x')],
            [[0, 1]])

    def test_varargs_and_bare_asterisk(self) -> None:
        self.assert_map(
            [ARG_STAR],
            [ARG_STAR, (ARG_NAMED, 'x')],
            [[0], []])
        self.assert_map(
            [ARG_STAR, 'x'],
            [ARG_STAR, (ARG_NAMED, 'x')],
            [[0], [1]])

    def test_keyword_varargs(self) -> None:
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

    def test_both_kinds_of_varargs(self) -> None:
        self.assert_map(
            [ARG_STAR, ARG_STAR2],
            [(ARG_POS, 'x'), (ARG_POS, 'y')],
            [[0, 1], [0, 1]])

    def test_special_cases(self) -> None:
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

    def assert_map(self,
                   caller_kinds_: List[Union[int, str]],
                   callee_kinds_: List[Union[int, Tuple[int, str]]],
                   expected: List[List[int]],
                   ) -> None:
        caller_kinds, caller_names = expand_caller_kinds(caller_kinds_)
        callee_kinds, callee_names = expand_callee_kinds(callee_kinds_)
        result = map_actuals_to_formals(
            caller_kinds,
            caller_names,
            callee_kinds,
            callee_names,
            lambda i: AnyType(TypeOfAny.special_form))
        assert_equal(result, expected)

    def assert_vararg_map(self,
                          caller_kinds: List[int],
                          callee_kinds: List[int],
                          expected: List[List[int]],
                          vararg_type: Type,
                          ) -> None:
        result = map_actuals_to_formals(
            caller_kinds,
            [],
            callee_kinds,
            [],
            lambda i: vararg_type)
        assert_equal(result, expected)


def expand_caller_kinds(kinds_or_names: List[Union[int, str]]
                        ) -> Tuple[List[int], List[Optional[str]]]:
    kinds = []
    names = []  # type: List[Optional[str]]
    for k in kinds_or_names:
        if isinstance(k, str):
            kinds.append(ARG_NAMED)
            names.append(k)
        else:
            kinds.append(k)
            names.append(None)
    return kinds, names


def expand_callee_kinds(kinds_and_names: List[Union[int, Tuple[int, str]]]
                        ) -> Tuple[List[int], List[Optional[str]]]:
    kinds = []
    names = []  # type: List[Optional[str]]
    for v in kinds_and_names:
        if isinstance(v, tuple):
            kinds.append(v[0])
            names.append(v[1])
        else:
            kinds.append(v)
            names.append(None)
    return kinds, names
