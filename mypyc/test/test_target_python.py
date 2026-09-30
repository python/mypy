"""Tests for targeting a Python build other than the running one."""

from __future__ import annotations

import os
import tempfile
import unittest

from mypyc.__main__ import extract_target_python
from mypyc.build import generate_c_extension_shim, get_mypy_config
from mypyc.codegen.emit import Emitter, EmitterContext
from mypyc.codegen.emitmodule import GroupGenerator
from mypyc.common import EXT_SUFFIX
from mypyc.namegen import NameGenerator
from mypyc.options import CompilerOptions, TargetPython, replace_ext_suffix_version


class TestTargetPython(unittest.TestCase):
    def test_parse(self) -> None:
        assert TargetPython.parse("3.13") == TargetPython((3, 13), False)
        assert TargetPython.parse("3.14t") == TargetPython((3, 14), True)
        assert TargetPython.parse("3.10") == TargetPython((3, 10), False)

    def test_parse_invalid(self) -> None:
        for target in ["3", "3.13x", "313", "2.7", "4.0", "3.9", "3.12t", "t"]:
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
            assert replace_ext_suffix_version(host, TargetPython.parse(target)) == expected

    def test_compiler_options(self) -> None:
        options = CompilerOptions(target_python=TargetPython((3, 14), True))
        assert options.capi_version == (3, 14)
        # Overriding only the C API version preserves free-threading
        options.capi_version = (3, 13)
        assert options.target_python == TargetPython((3, 13), True)
        options = CompilerOptions(capi_version=(3, 12), target_python=TargetPython((3, 14), True))
        assert options.target_python == TargetPython((3, 12), True)

    def test_extract_target_python(self) -> None:
        assert extract_target_python(["a.py", "--strict"]) == (["a.py", "--strict"], None)
        assert extract_target_python(["--target-python", "3.14t", "a.py"]) == (["a.py"], "3.14t")
        assert extract_target_python(["a.py", "--target-python=3.13"]) == (["a.py"], "3.13")

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

    def test_extension_shim(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            for free_threaded in (False, True):
                path = generate_c_extension_shim(
                    "pkg.mod", "mod", tmp, "group", TargetPython((3, 14), free_threaded)
                )
                with open(path) as f:
                    shim = f.read()
                assert ("PyModuleDef_Init" in shim) == free_threaded, shim
                os.remove(path)

    def test_python_version_rejected(self) -> None:
        for args in (["--python-version", "3.13", "a.py"], ["--python-version=3.13", "a.py"]):
            with self.assertRaises(SystemExit) as cm:
                get_mypy_config(args, None, CompilerOptions(), None)
            assert str(cm.exception.code) == "error: mypyc does not accept --python-version"
