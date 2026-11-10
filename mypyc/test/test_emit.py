from __future__ import annotations

import unittest

from mypyc.codegen.emit import Emitter, EmitterContext
from mypyc.ir.class_ir import ClassIR
from mypyc.ir.ops import BasicBlock, Register, Value
from mypyc.ir.rtypes import (
    RInstance,
    RTuple,
    RUnion,
    bool_rprimitive,
    int64_rprimitive,
    int_rprimitive,
    list_rprimitive,
    none_rprimitive,
    object_rprimitive,
    str_rprimitive,
)
from mypyc.irbuild.vtable import compute_vtable
from mypyc.namegen import NameGenerator
from mypyc.options import TargetPython


class TestEmitter(unittest.TestCase):
    def setUp(self) -> None:
        self.n = Register(int_rprimitive, "n")
        self.context = EmitterContext(NameGenerator([["mod"]]), True)
        self.emitter = Emitter(self.context, {})

        ir = ClassIR("A", "mod")
        compute_vtable(ir)
        ir.mro = [ir]
        self.instance_a = RInstance(ir)

    def test_label(self) -> None:
        assert self.emitter.label(BasicBlock(4)) == "CPyL4"

    def test_private_frame_bitmap_access(self) -> None:
        cl = self.instance_a.class_ir
        cl.attributes = {"value": int64_rprimitive}
        cl.bitmap_attrs = ["value"]
        cl.is_generated = True
        cl.has_private_generator_frame = True
        cl.has_running_flag = True
        cl.needs_getseters = False
        emitter = Emitter(
            EmitterContext(
                NameGenerator([["mod"]]), True, target_python=TargetPython((3, 14), True)
            )
        )
        # Exposing the frame or removing its execution guard requires atomics again.
        for changed in (
            None,
            "needs_getseters",
            "has_running_flag",
            "has_private_generator_frame",
        ):
            with self.subTest(changed=changed):
                if changed is not None:
                    previous = getattr(cl, changed)
                    setattr(cl, changed, not previous)
                emitter.fragments.clear()
                emitter.emit_attr_bitmap_set("value", "obj", int64_rprimitive, cl, "value")
                emitter.emit_attr_bitmap_clear("obj", int64_rprimitive, cl, "value")
                emitter.emit_undefined_attr_check(
                    int64_rprimitive, "value", "==", "obj", "value", cl
                )
                generated = "".join(emitter.fragments)
                if changed is None:
                    assert "((mod___AObject *)obj)->bitmap |= 1;" in generated
                    assert "((mod___AObject *)obj)->bitmap &= ~1;" in generated
                    assert "!(((mod___AObject *)obj)->bitmap & 1)" in generated
                    assert "_Py_atomic_" not in generated
                else:
                    assert "_Py_atomic_or_uint32" in generated
                    assert "_Py_atomic_and_uint32" in generated
                    assert "_Py_atomic_load_uint32" in generated
                    setattr(cl, changed, previous)

    def test_reg(self) -> None:
        names: dict[Value, str] = {self.n: "n"}
        emitter = Emitter(self.context, names)
        assert emitter.reg(self.n) == "cpy_r_n"

    def test_object_annotation(self) -> None:
        assert self.emitter.object_annotation("hello, world", "line;") == " /* 'hello, world' */"
        assert self.emitter.object_annotation(42, "line;") == " /* 42 */"
        assert self.emitter.object_annotation((1, "x", None), "line;") == " /* (1, 'x', None) */"
        # Annotations containing illegal C comment characters are dropped.
        assert self.emitter.object_annotation("a /* b */ c", "line;") == ""

    def test_object_annotation_frozenset_is_deterministic(self) -> None:
        assert (
            self.emitter.object_annotation(frozenset({"self", "cls"}), "line;")
            == self.emitter.object_annotation(frozenset({"cls", "self"}), "line;")
            == " /* frozenset({'cls', 'self'}) */"
        )
        assert (
            self.emitter.object_annotation((frozenset({"b", "a"}),), "line;")
            == self.emitter.object_annotation((frozenset({"a", "b"}),), "line;")
            == " /* (frozenset({'a', 'b'}),) */"
        )
        assert self.emitter.object_annotation(frozenset(), "line;") == " /* frozenset() */"

    def test_emit_line(self) -> None:
        emitter = self.emitter
        emitter.emit_line("line;")
        emitter.emit_line("a {")
        emitter.emit_line("f();")
        emitter.emit_line("}")
        assert emitter.fragments == ["line;\n", "a {\n", "    f();\n", "}\n"]
        emitter = Emitter(self.context, {})
        emitter.emit_line("CPyStatics[0];", ann="hello, world")
        emitter.emit_line("CPyStatics[1];", ann=42)
        assert emitter.fragments[0] == "CPyStatics[0]; /* 'hello, world' */\n"
        assert emitter.fragments[1] == "CPyStatics[1]; /* 42 */\n"

    def test_emit_line_with_indented_braces(self) -> None:
        self.emitter.emit_lines(
            "if (outer)",
            "    if (inner) { ",
            "    f();",
            "    } else {",
            "    g();",
            "    }",
            "h();",
        )
        self.assert_output(
            "if (outer)\n"
            "    if (inner) { \n"
            "        f();\n"
            "    } else {\n"
            "        g();\n"
            "    }\n"
            "h();\n"
        )

    def test_emit_undefined_value_for_simple_type(self) -> None:
        emitter = self.emitter
        assert emitter.c_undefined_value(int_rprimitive) == "CPY_INT_TAG"
        assert emitter.c_undefined_value(str_rprimitive) == "NULL"
        assert emitter.c_undefined_value(bool_rprimitive) == "2"

    def test_emit_undefined_value_for_tuple(self) -> None:
        emitter = self.emitter
        assert (
            emitter.c_undefined_value(RTuple([str_rprimitive, int_rprimitive, bool_rprimitive]))
            == "(tuple_T3OIC) { NULL, CPY_INT_TAG, 2 }"
        )
        assert emitter.c_undefined_value(RTuple([str_rprimitive])) == "(tuple_T1O) { NULL }"
        assert (
            emitter.c_undefined_value(RTuple([RTuple([str_rprimitive]), bool_rprimitive]))
            == "(tuple_T2T1OC) { { NULL }, 2 }"
        )

    def test_emit_inc_ref_object(self) -> None:
        self.emitter.emit_inc_ref("x", object_rprimitive)
        self.assert_output("CPy_INCREF(x);\n")

    def test_emit_inc_ref_int(self) -> None:
        self.emitter.emit_inc_ref("x", int_rprimitive)
        self.assert_output("CPyTagged_INCREF(x);\n")

    def test_emit_inc_ref_rare(self) -> None:
        self.emitter.emit_inc_ref("x", object_rprimitive, rare=True)
        self.assert_output("CPy_INCREF(x);\n")
        self.emitter.emit_inc_ref("x", int_rprimitive, rare=True)
        self.assert_output("CPyTagged_IncRef(x);\n")

    def test_emit_inc_ref_list(self) -> None:
        self.emitter.emit_inc_ref("x", list_rprimitive)
        if TargetPython.host().have_immortal:
            self.assert_output("CPy_INCREF_NO_IMM(x);\n")
        else:
            self.assert_output("CPy_INCREF(x);\n")

    def test_emit_inc_ref_instance(self) -> None:
        self.emitter.emit_inc_ref("x", self.instance_a)
        if TargetPython.host().have_immortal:
            self.assert_output("CPy_INCREF_NO_IMM(x);\n")
        else:
            self.assert_output("CPy_INCREF(x);\n")

    def test_emit_inc_ref_optional(self) -> None:
        optional = RUnion([self.instance_a, none_rprimitive])
        self.emitter.emit_inc_ref("o", optional)
        self.assert_output("CPy_INCREF(o);\n")

    def test_emit_dec_ref_object(self) -> None:
        self.emitter.emit_dec_ref("x", object_rprimitive)
        self.assert_output("CPy_DECREF(x);\n")
        self.emitter.emit_dec_ref("x", object_rprimitive, is_xdec=True)
        self.assert_output("CPy_XDECREF(x);\n")

    def test_emit_dec_ref_int(self) -> None:
        self.emitter.emit_dec_ref("x", int_rprimitive)
        self.assert_output("CPyTagged_DECREF(x);\n")
        self.emitter.emit_dec_ref("x", int_rprimitive, is_xdec=True)
        self.assert_output("CPyTagged_XDECREF(x);\n")

    def test_emit_dec_ref_rare(self) -> None:
        self.emitter.emit_dec_ref("x", object_rprimitive, rare=True)
        self.assert_output("CPy_DecRef(x);\n")
        self.emitter.emit_dec_ref("x", int_rprimitive, rare=True)
        self.assert_output("CPyTagged_DecRef(x);\n")

    def test_emit_dec_ref_list(self) -> None:
        self.emitter.emit_dec_ref("x", list_rprimitive)
        if TargetPython.host().have_immortal:
            self.assert_output("CPy_DECREF_NO_IMM(x);\n")
        else:
            self.assert_output("CPy_DECREF(x);\n")
        self.emitter.emit_dec_ref("x", list_rprimitive, is_xdec=True)
        if TargetPython.host().have_immortal:
            self.assert_output("CPy_XDECREF_NO_IMM(x);\n")
        else:
            self.assert_output("CPy_XDECREF(x);\n")

    def test_emit_dec_ref_instance(self) -> None:
        self.emitter.emit_dec_ref("x", self.instance_a)
        if TargetPython.host().have_immortal:
            self.assert_output("CPy_DECREF_NO_IMM(x);\n")
        else:
            self.assert_output("CPy_DECREF(x);\n")
        self.emitter.emit_dec_ref("x", self.instance_a, is_xdec=True)
        if TargetPython.host().have_immortal:
            self.assert_output("CPy_XDECREF_NO_IMM(x);\n")
        else:
            self.assert_output("CPy_XDECREF(x);\n")

    def test_emit_dec_ref_optional(self) -> None:
        optional = RUnion([self.instance_a, none_rprimitive])
        self.emitter.emit_dec_ref("o", optional)
        self.assert_output("CPy_DECREF(o);\n")

    def assert_output(self, expected: str) -> None:
        assert "".join(self.emitter.fragments) == expected
        self.emitter.fragments = []
