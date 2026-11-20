"""Tests for constant folding of huge operands."""

from __future__ import annotations

from mypy.constant_fold import constant_fold_binary_float_op, constant_fold_binary_int_op
from mypy.test.helpers import Suite

BIG = 2**2000


class ConstantFoldOverflowSuite(Suite):
    """Folding is an optimization: when a result cannot be built, it must yield None."""

    def test_int_div_overflow(self) -> None:
        assert constant_fold_binary_int_op("/", BIG, 3) is None

    def test_int_lshift_huge_count(self) -> None:
        assert constant_fold_binary_int_op("<<", 1, 2**70) is None

    def test_float_ops_with_huge_int(self) -> None:
        for op in ("+", "-", "*", "/", "//", "%"):
            assert constant_fold_binary_float_op(op, BIG, 1.0) is None, op

    def test_small_operands_still_fold(self) -> None:
        assert constant_fold_binary_int_op("/", 6, 3) == 2.0
        assert constant_fold_binary_int_op("<<", 1, 4) == 16
        assert constant_fold_binary_float_op("+", 1, 2.5) == 3.5
        assert constant_fold_binary_float_op("**", 2.0, 3) == 8.0
