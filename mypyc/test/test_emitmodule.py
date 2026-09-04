from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pytest

from mypy import build
from mypy.options import Options
from mypyc.build import construct_groups
from mypyc.codegen import emitmodule
from mypyc.common import (
    ENV_ATTR_NAME,
    GENERATOR_ATTRIBUTE_PREFIX,
    NEXT_LABEL_ATTR_NAME,
    TEMP_ATTR_NAME,
)
from mypyc.errors import Errors
from mypyc.ir.rtypes import RInstance
from mypyc.irbuild.mapper import Mapper
from mypyc.options import CompilerOptions


class FakeSCC:
    def __init__(self, mod_ids: list[str]) -> None:
        self.mod_ids = mod_ids


class TestEmitModule(unittest.TestCase):
    def test_separate_generator_environment_keeps_private_frame_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            module_path = tmp_path / "mod.py"
            module_path.write_text(
                """\
from typing import Generator

def make() -> str:
    return "left"

def outer() -> Generator[str, str, str]:
    def nested(value: str) -> Generator[str, str, str]:
        return make() + (yield value)
    return nested("right")
""",
                encoding="utf-8",
            )

            sources = [build.BuildSource(str(module_path), "mod", None)]
            options = Options()
            options.preserve_asts = True
            options.mypy_path = [str(tmp_path)]
            options.cache_dir = str(tmp_path / ".mypy_cache")
            options.per_module_options["mod"] = {"mypyc": True}

            compiler_options = CompilerOptions(strict_traceback_checks=True)
            groups = construct_groups(
                sources, False, use_shared_lib=True, group_name_override=None
            )
            result = emitmodule.parse_and_typecheck(sources, options, compiler_options, groups)
            try:
                group_map = {
                    source.module: lib_name for group, lib_name in groups for source in group
                }
                errors = Errors(options)
                modules = emitmodule.compile_modules_to_ir(
                    result, Mapper(group_map), compiler_options, errors
                )
                assert errors.num_errors == 0, errors.new_messages()
            finally:
                result.manager.metastore.close()

            classes = [cl for module in modules.values() for cl in module.classes]
            (generator,) = [cl for cl in classes if cl.has_running_flag]
            assert generator.has_private_generator_frame
            assert generator.attrs_are_thread_confined()

            env_type = generator.attributes[ENV_ATTR_NAME]
            assert isinstance(env_type, RInstance)
            environment = env_type.class_ir
            assert not environment.attrs_are_thread_confined()

            private_attrs = set(generator.attributes)
            shared_attrs = set(environment.attributes)
            assert NEXT_LABEL_ATTR_NAME in private_attrs
            assert NEXT_LABEL_ATTR_NAME in generator.attrs_with_defaults
            assert NEXT_LABEL_ATTR_NAME not in shared_attrs
            assert any(name.startswith(TEMP_ATTR_NAME) for name in private_attrs)
            assert not any(name.startswith(TEMP_ATTR_NAME) for name in shared_attrs)
            assert GENERATOR_ATTRIBUTE_PREFIX + "value" in shared_attrs
            assert GENERATOR_ATTRIBUTE_PREFIX + "value" not in private_attrs

    def test_compile_modules_to_ir_orders_scc_members_deterministically(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir, pytest.MonkeyPatch.context() as monkeypatch:
            tmp_path = Path(tmp_dir)
            a_py = tmp_path / "a.py"
            b_py = tmp_path / "b.py"
            a_py.write_text("import b\n\nclass A: pass\nclass C(A): pass\n", encoding="utf-8")
            b_py.write_text(
                "import a\n\nclass B(a.A): pass\nclass D(a.A): pass\n", encoding="utf-8"
            )

            sources = [
                build.BuildSource(str(a_py), "a", None),
                build.BuildSource(str(b_py), "b", None),
            ]
            options = Options()
            options.preserve_asts = True
            options.mypy_path = [str(tmp_path)]
            options.cache_dir = str(tmp_path / ".mypy_cache")
            for source in sources:
                options.per_module_options.setdefault(source.module, {})["mypyc"] = True

            compiler_options = CompilerOptions(strict_traceback_checks=True)
            groups = construct_groups(
                sources, False, use_shared_lib=True, group_name_override=None
            )
            result = emitmodule.parse_and_typecheck(sources, options, compiler_options, groups)
            try:
                group_map = {
                    source.module: lib_name for group, lib_name in groups for source in group
                }
                children_by_order = []
                for order in (["a", "b"], ["b", "a"]):
                    monkeypatch.setattr(
                        emitmodule,
                        "sorted_components",
                        lambda graph, order=order: [FakeSCC(order)],
                    )
                    mapper = Mapper(group_map)
                    errors = Errors(options)
                    modules = emitmodule.compile_modules_to_ir(
                        result, mapper, compiler_options, errors
                    )
                    assert errors.num_errors == 0, errors.new_messages()
                    classes = {
                        cl.fullname: cl for module in modules.values() for cl in module.classes
                    }
                    children = classes["a.A"].children
                    assert children is not None
                    children_by_order.append([child.fullname for child in children])

                assert children_by_order[1] == children_by_order[0]
            finally:
                result.manager.metastore.close()
