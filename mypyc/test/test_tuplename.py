from __future__ import annotations

import unittest

from mypyc.ir.class_ir import ClassIR
from mypyc.ir.rtypes import (
    RInstance,
    RTuple,
    RUnion,
    bool_rprimitive,
    int16_rprimitive,
    int32_rprimitive,
    int64_rprimitive,
    int_rprimitive,
    list_rprimitive,
    object_rprimitive,
    uint8_rprimitive,
    uint16_rprimitive,
    uint32_rprimitive,
    uint64_rprimitive,
)


class TestTupleNames(unittest.TestCase):
    def setUp(self) -> None:
        self.inst_a = RInstance(ClassIR("A", "__main__"))
        self.inst_b = RInstance(ClassIR("B", "__main__"))

    def test_names(self) -> None:
        assert RTuple([int_rprimitive, int_rprimitive]).unique_id == "T2II"
        assert RTuple([int64_rprimitive, int32_rprimitive]).unique_id == "T284"
        assert RTuple([int32_rprimitive, uint32_rprimitive]).unique_id == "T24U4"
        assert RTuple([int64_rprimitive, uint64_rprimitive]).unique_id == "T28U8"
        assert RTuple([int16_rprimitive, uint16_rprimitive]).unique_id == "T22U2"
        assert RTuple([uint8_rprimitive]).unique_id == "T1U1"
        assert RTuple([list_rprimitive, object_rprimitive, self.inst_a]).unique_id == "T3OOO"
        assert RTuple([list_rprimitive, object_rprimitive, self.inst_b]).unique_id == "T3OOO"
        assert RTuple([]).unique_id == "T0"
        assert (
            RTuple([RTuple([]), RTuple([int_rprimitive, int_rprimitive])]).unique_id == "T2T0T2II"
        )
        assert (
            RTuple([bool_rprimitive, RUnion([bool_rprimitive, int_rprimitive])]).unique_id
            == "T2CO"
        )
