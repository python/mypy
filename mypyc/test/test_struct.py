import unittest

from mypyc.ir.rtypes import (
    RStruct, bool_rprimitive, int64_rprimitive, int32_rprimitive, object_rprimitive
)
from mypyc.common import IS_32_BIT_PLATFORM


class TestStruct(unittest.TestCase):
    def test_struct_offsets(self) -> None:
        # test per-member alignment
        r1 = RStruct("", [], [bool_rprimitive, int32_rprimitive, int64_rprimitive])
        assert r1.size == 16
        assert r1.offsets == [0, 4, 8]

        # test final alignment
        r2 = RStruct("", [], [int32_rprimitive, bool_rprimitive])
        r3 = RStruct("", [], [int64_rprimitive, bool_rprimitive])
        assert r2.offsets == [0, 4]
        assert r3.offsets == [0, 8]
        if IS_32_BIT_PLATFORM:
            assert r2.size == 8
            assert r3.size == 12
        else:
            assert r2.size == 8
            assert r3.size == 16

    def test_struct_str(self) -> None:
        r = RStruct("Foo", ["a", "b"],
                    [bool_rprimitive, object_rprimitive])
        assert str(r) == "Foo{a:bool, b:object}"
        assert repr(r) == "<RStruct Foo{a:<RPrimitive builtins.bool>, " \
                          "b:<RPrimitive builtins.object>}>"
