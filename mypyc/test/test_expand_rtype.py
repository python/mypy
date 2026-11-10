import unittest

from mypyc.ir.class_ir import ClassIR
from mypyc.ir.rtypes import (
    RInstance,
    RTuple,
    RTypeVar,
    RUnion,
    RVec,
    int_rprimitive,
    str_rprimitive,
    void_rtype,
)
from mypyc.rt_expandtype import expand_rtype


class TestExpandRType(unittest.TestCase):
    def test_trivial(self) -> None:
        assert expand_rtype(str_rprimitive, []) == str_rprimitive
        assert expand_rtype(str_rprimitive, [int_rprimitive]) == str_rprimitive
        assert expand_rtype(void_rtype, []) == void_rtype

    def test_instance(self) -> None:
        inst = RInstance(ClassIR("A", "__main__"))
        assert expand_rtype(inst, [int_rprimitive]) == inst

    def test_simple_expansion(self) -> None:
        assert expand_rtype(RTypeVar(0), [str_rprimitive]) == str_rprimitive

    def test_tuple_expansion(self) -> None:
        assert expand_rtype(
            RTuple([RTypeVar(0), RTypeVar(1)]), [str_rprimitive, int_rprimitive]
        ) == RTuple([str_rprimitive, int_rprimitive])

    def test_union_expansion(self) -> None:
        assert expand_rtype(
            RUnion([RTypeVar(0), RTypeVar(1)]), [str_rprimitive, int_rprimitive]
        ) == RUnion([str_rprimitive, int_rprimitive])

    def test_vec_expansion(self) -> None:
        assert expand_rtype(RVec(RTypeVar(0)), [str_rprimitive]) == RVec(str_rprimitive)

    def test_nested_expansion(self) -> None:
        typ = RUnion([RTuple([RVec(RTypeVar(0)), RTypeVar(1)]), RVec(RVec(RTypeVar(0)))])
        expected = RUnion(
            [RTuple([RVec(str_rprimitive), int_rprimitive]), RVec(RVec(str_rprimitive))]
        )
        assert expand_rtype(typ, [str_rprimitive, int_rprimitive]) == expected
