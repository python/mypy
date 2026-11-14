"""Test the bit set representation used by data-flow analyses."""

from __future__ import annotations

import unittest
from collections.abc import Set as AbstractSet

from mypyc.analysis.dataflow import BitIndex, BitSet


def make(index: BitIndex[str], values: set[str]) -> BitSet[str]:
    return BitSet(index.mask(values), index)


class TestBitSet(unittest.TestCase):
    def setUp(self) -> None:
        self.index: BitIndex[str] = BitIndex()
        # Make the index large enough so that masks don't fit in a machine word.
        self.many = {f"v{i}" for i in range(200)}
        self.index.mask(self.many)

    def test_basic(self) -> None:
        empty = make(self.index, set())
        assert not empty
        assert len(empty) == 0
        assert set(empty) == set()

        s = make(self.index, {"v1", "v150", "new"})
        assert s
        assert len(s) == 3
        assert "v1" in s
        assert "v150" in s
        assert "new" in s
        assert "v2" not in s
        assert "unknown" not in s
        assert set(s) == {"v1", "v150", "new"}
        assert isinstance(s, AbstractSet)

        full = make(self.index, self.many)
        assert len(full) == 200
        assert set(full) == self.many

    def test_operations_with_same_index(self) -> None:
        a = make(self.index, {"v1", "v2", "v3", "v199"})
        b = make(self.index, {"v2", "v3", "v4", "v100"})
        for result, expected in [
            (a - b, {"v1", "v199"}),
            (a & b, {"v2", "v3"}),
            (a | b, {"v1", "v2", "v3", "v4", "v100", "v199"}),
        ]:
            assert isinstance(result, BitSet)
            assert set(result) == expected

    def test_operations_with_other_sets(self) -> None:
        a = make(self.index, {"v1", "v2", "v3", "v199"})
        other_index: BitIndex[str] = BitIndex()
        for other in [
            {"v2", "v3", "v4", "x"},
            make(other_index, {"v2", "v3", "v4", "x"}),
            self.many | {"x"},
            make(other_index, self.many | {"x"}),
        ]:
            for result, expected in [
                (a - other, set(a) - set(other)),
                (other - a, set(other) - set(a)),
                (a & other, set(a) & set(other)),
                (other & a, set(other) & set(a)),
                (a | other, set(a) | set(other)),
                (other | a, set(other) | set(a)),
            ]:
                assert set(result) == expected

    def test_reflected_operations_return_sets(self) -> None:
        # Compiled code relies on set <op> AbstractSet returning a set.
        a = make(self.index, {"v1", "v2"})
        assert type({"v1"} - a) is set
        assert type({"v1"} & a) is set
        assert type({"v1"} | a) is set
