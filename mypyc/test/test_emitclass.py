from __future__ import annotations

import unittest

from mypyc.analysis.attrdefined import detect_undefined_bitmap
from mypyc.codegen.emitclass import getter_name, setter_name, slot_key
from mypyc.ir.class_ir import ClassIR
from mypyc.ir.rtypes import int32_rprimitive
from mypyc.namegen import NameGenerator


class TestEmitClass(unittest.TestCase):
    def test_slot_key(self) -> None:
        attrs = ["__add__", "__radd__", "__rshift__", "__rrshift__", "__setitem__", "__delitem__"]
        s = sorted(attrs, key=lambda x: slot_key(x))
        # __delitem__ and reverse methods should come last.
        assert s == [
            "__add__",
            "__rshift__",
            "__setitem__",
            "__delitem__",
            "__radd__",
            "__rrshift__",
        ]

    def test_setter_name(self) -> None:
        cls = ClassIR(module_name="testing", name="SomeClass")
        generator = NameGenerator([["mod"]])

        # This should never be `setup`, as it will conflict with the class `setup`
        assert setter_name(cls, "up", generator) == "testing___SomeClass_set_up"

    def test_getter_name(self) -> None:
        cls = ClassIR(module_name="testing", name="SomeClass")
        generator = NameGenerator([["mod"]])

        assert getter_name(cls, "down", generator) == "testing___SomeClass_get_down"

    def test_bitmap_attrs_stable_across_repeat_analysis(self) -> None:
        # Regression: detect_undefined_bitmap used to mutate cl.bitmap_attrs
        # in place, so under separate=True (one SCC per group) a shared base
        # class would accumulate duplicate entries as each subclass's SCC
        # walked into it, growing the emitted struct between builds.
        base = ClassIR("Base", "mod")
        base.attributes = {"i": int32_rprimitive}
        sub = ClassIR("Sub", "mod")
        sub.attributes = {"j": int32_rprimitive}
        base.mro = base.base_mro = [base]
        sub.mro = sub.base_mro = [sub, base]
        base.children = [sub]

        detect_undefined_bitmap(sub, seen=set())
        for _ in range(10):
            detect_undefined_bitmap(sub, seen=set())
        assert base.bitmap_attrs == ["i"]
        assert sub.bitmap_attrs == ["i", "j"]
