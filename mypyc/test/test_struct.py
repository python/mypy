import unittest

from mypyc.ir.rtypes import (
    RStruct, bool_rprimitive, int64_rprimitive, int32_rprimitive, object_rprimitive, StructInfo,
    int_rprimitive
)
from mypyc.rt_subtype import is_runtime_subtype


class TestStruct(unittest.TestCase):
    def test_struct_offsets(self) -> None:
        # test per-member alignment
        info = StructInfo("", [], [bool_rprimitive, int32_rprimitive, int64_rprimitive])
        r = RStruct(info)
        assert r.size == 16
        assert r.offsets == [0, 4, 8]

        # test final alignment
        info1 = StructInfo("", [], [bool_rprimitive, bool_rprimitive])
        r1 = RStruct(info1)
        assert r1.size == 2
        assert r1.offsets == [0, 1]
        info2 = StructInfo("", [], [int32_rprimitive, bool_rprimitive])
        r2 = RStruct(info2)
        info3 = StructInfo("", [], [int64_rprimitive, bool_rprimitive])
        r3 = RStruct(info3)
        assert r2.offsets == [0, 4]
        assert r3.offsets == [0, 8]
        assert r2.size == 8
        assert r3.size == 16

        info4 = StructInfo("", [], [bool_rprimitive, bool_rprimitive,
                              bool_rprimitive, int32_rprimitive])
        r4 = RStruct(info4)
        assert r4.size == 8
        assert r4.offsets == [0, 1, 2, 4]

        # test nested struct
        info5 = StructInfo("", [], [bool_rprimitive, r])
        r5 = RStruct(info5)
        assert r5.offsets == [0, 8]
        assert r5.size == 24
        info6 = StructInfo("", [], [int32_rprimitive, r5])
        r6 = RStruct(info6)
        assert r6.offsets == [0, 8]
        assert r6.size == 32
        # test nested struct with alignment less than 8
        info7 = StructInfo("", [], [bool_rprimitive, r4])
        r7 = RStruct(info7)
        assert r7.offsets == [0, 4]
        assert r7.size == 12

    def test_struct_str(self) -> None:
        info = StructInfo("Foo", ["a", "b"],
                    [bool_rprimitive, object_rprimitive])
        r = RStruct(info)
        assert str(r) == "Foo{a:bool, b:object}"
        assert repr(r) == "<RStruct Foo{a:<RPrimitive builtins.bool>, " \
                          "b:<RPrimitive builtins.object>}>"
        info1 = StructInfo("Bar", ["c"], [int32_rprimitive])
        r1 = RStruct(info1)
        assert str(r1) == "Bar{c:int32}"
        assert repr(r1) == "<RStruct Bar{c:<RPrimitive int32>}>"
        info2 = StructInfo("Baz", [], [])
        r2 = RStruct(info2)
        assert str(r2) == "Baz{}"
        assert repr(r2) == "<RStruct Baz{}>"

    def test_runtime_subtype(self) -> None:
        # right type to check with
        info = StructInfo("Foo", ["a", "b"],
                    [bool_rprimitive, int_rprimitive])
        r = RStruct(info)

        # using the same StructInfo
        r1 = RStruct(info)

        # names different
        info2 = StructInfo("Bar", ["c", "b"],
                    [bool_rprimitive, int_rprimitive])
        r2 = RStruct(info2)

        # name different
        info3 = StructInfo("Baz", ["a", "b"],
                    [bool_rprimitive, int_rprimitive])
        r3 = RStruct(info3)

        # type different
        info4 = StructInfo("FooBar", ["a", "b"],
                    [bool_rprimitive, int32_rprimitive])
        r4 = RStruct(info4)

        # number of types different
        info5 = StructInfo("FooBarBaz", ["a", "b", "c"],
                    [bool_rprimitive, int_rprimitive, bool_rprimitive])
        r5 = RStruct(info5)

        assert is_runtime_subtype(r1, r) is True
        assert is_runtime_subtype(r2, r) is False
        assert is_runtime_subtype(r3, r) is False
        assert is_runtime_subtype(r4, r) is False
        assert is_runtime_subtype(r5, r) is False
