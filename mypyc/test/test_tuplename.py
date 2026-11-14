from __future__ import annotations

import unittest

from mypyc.ir.class_ir import ClassIR
from mypyc.ir.rtypes import (
    RInstance,
    RTuple,
    RUnion,
    bool_rprimitive,
    int8_rprimitive,
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
        assert RTuple([int64_rprimitive, int32_rprimitive]).unique_id == "T2S8S4"
        assert RTuple([int32_rprimitive, uint32_rprimitive]).unique_id == "T2S4U4"
        assert RTuple([int64_rprimitive, uint64_rprimitive]).unique_id == "T2S8U8"
        assert RTuple([int16_rprimitive, uint16_rprimitive]).unique_id == "T2S2U2"
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

    def test_names_unambiguous(self) -> None:
        # Previously both of these were named "T2T11T11IIIIIIIIIII", since the
        # i8 item code "1" was indistinguishable from the tuple length.
        t1 = RTuple([RTuple([int8_rprimitive]), RTuple([int_rprimitive] * 11)])
        t2 = RTuple([RTuple([RTuple([int8_rprimitive])] + [int_rprimitive] * 10), int_rprimitive])
        assert t1.unique_id == "T2T1S1T11IIIIIIIIIII"
        assert t2.unique_id == "T2T11T1S1IIIIIIIIIII"
