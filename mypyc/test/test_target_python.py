"""Tests for targeting a Python build other than the running one."""

from __future__ import annotations

import os
import tempfile
import unittest

from mypyc.build import get_mypy_config
from mypyc.codegen.emit import Emitter, EmitterContext
from mypyc.codegen.emitmodule import GroupGenerator
from mypyc.common import EXT_SUFFIX
from mypyc.ir.rtypes import RUnion, list_rprimitive, object_rprimitive
from mypyc.namegen import NameGenerator
from mypyc.options import CompilerOptions, TargetPython, replace_ext_suffix_version
from mypyc.test.testutil import infer_target_python_from_test_name


class TestTargetPython(unittest.TestCase):
    def test_parse(self) -> None:
        assert TargetPython.parse("3.13") == TargetPython((3, 13), False)
        assert TargetPython.parse("3.14t") == TargetPython((3, 14), True)
        assert TargetPython.parse("3.10") == TargetPython((3, 10), False)

    def test_parse_invalid(self) -> None:
        for target in ["3", "3.13x", "313", "2.7", "4.0", "3.9", "3.12t", "t", "3.10t"]:
            with self.assertRaises(ValueError, msg=target):
                TargetPython.parse(target)

    def test_str(self) -> None:
        assert str(TargetPython((3, 13), False)) == "3.13"
        assert str(TargetPython((3, 14), True)) == "3.14t"

    def test_have_immortal(self) -> None:
        assert not TargetPython((3, 11)).have_immortal
        assert TargetPython((3, 12)).have_immortal

    def test_ext_suffix(self) -> None:
        assert TargetPython.host().ext_suffix == EXT_SUFFIX
        for host, target, expected in [
            (".cpython-313-x86_64-linux-gnu.so", "3.14t", ".cpython-314t-x86_64-linux-gnu.so"),
            (".cpython-314t-darwin.so", "3.13", ".cpython-313-darwin.so"),
            (".cp313-win_amd64.pyd", "3.14t", ".cp314t-win_amd64.pyd"),
            ("_d.cp313t-win_amd64.pyd", "3.12", "_d.cp312-win_amd64.pyd"),
        ]:
            parsed = TargetPython.parse(target)
            result = replace_ext_suffix_version(host, parsed.version, parsed.free_threaded)
            assert result == expected
        for suffix in [".so", ".abi3.so", ".pypy310-pp73-x86_64-linux-gnu.so"]:
            with self.assertRaises(ValueError):
                replace_ext_suffix_version(suffix, (3, 14), True)

    def test_may_be_immortal(self) -> None:
        old, new = TargetPython((3, 11)), TargetPython((3, 12))
        assert not object_rprimitive.may_be_immortal(old)
        assert object_rprimitive.may_be_immortal(new)
        assert not list_rprimitive.may_be_immortal(new)
        assert RUnion([list_rprimitive, object_rprimitive]).may_be_immortal(new)

    def test_emit_ref_count_ops(self) -> None:
        def emit(target: TargetPython) -> str:
            emitter = Emitter(EmitterContext(NameGenerator([["mod"]]), True, target_python=target))
            emitter.emit_inc_ref("x", list_rprimitive)
            emitter.emit_dec_ref("x", list_rprimitive)
            return "".join(emitter.fragments)

        assert emit(TargetPython((3, 11))) == "CPy_INCREF(x);\nCPy_DECREF(x);\n"
        assert emit(TargetPython((3, 12))) == "CPy_INCREF_NO_IMM(x);\nCPy_DECREF_NO_IMM(x);\n"

    def test_invalid_target(self) -> None:
        for version, free_threaded in [((3, 9), False), ((2, 7), False), ((3, 12), True)]:
            with self.assertRaises(ValueError):
                TargetPython(version, free_threaded)

    def test_infer_target_python_from_test_name(self) -> None:
        assert infer_target_python_from_test_name("testFoo") == TargetPython((3, 10))
        assert infer_target_python_from_test_name("testFoo_withgil") == TargetPython((3, 10))
        assert infer_target_python_from_test_name("testFoo_nogil") == TargetPython((3, 13), True)
        assert infer_target_python_from_test_name("testFoo_python3_14_nogil") == TargetPython(
            (3, 14), True
        )
        assert infer_target_python_from_test_name("testFoo_python3_12") == TargetPython((3, 12))

    def test_module_def_slots(self) -> None:
        def slots(target: TargetPython) -> str:
            context = EmitterContext(NameGenerator([["mod"]]), True, target_python=target)
            emitter = Emitter(context)
            generator = GroupGenerator({}, {}, None, {}, context.names, CompilerOptions())
            generator.emit_module_def_slots(emitter, "prefix", "mod")
            return "".join(emitter.fragments)

        assert "Py_mod_gil" not in slots(TargetPython((3, 12)))
        assert "Py_mod_multiple_interpreters" in slots(TargetPython((3, 12)))
        assert "Py_mod_gil" in slots(TargetPython((3, 13)))

    def test_python_version_rejected(self) -> None:
        for args in (["--python-version", "3.13", "a.py"], ["--python-version=3.13", "a.py"]):
            with self.assertRaises(SystemExit) as cm:
                get_mypy_config(args, None, CompilerOptions(), None)
            assert str(cm.exception.code) == "error: mypyc does not accept --python-version"

    def test_mypy_python_version_follows_target(self) -> None:
        # This is used by mypyc_build(), which is how a target is selected.
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "a.py")
            with open(path, "w") as f:
                f.write("x = 1\n")
            options = CompilerOptions(target_python=TargetPython((3, 14), True))
            _, _, mypy_options = get_mypy_config([path], None, options, None)
            assert mypy_options.python_version == (3, 14)
