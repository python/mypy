from __future__ import annotations

import unittest

from mypyc.common import (
    ENV_ATTR_NAME,
    GENERATOR_ATTRIBUTE_PREFIX,
    NEXT_LABEL_ATTR_NAME,
    TEMP_ATTR_NAME,
)
from mypyc.ir.rtypes import RInstance
from mypyc.test.testutil import build_ir_for_single_file2
from mypyc.transform.spill import insert_spills


class TestSpill(unittest.TestCase):
    def test_separate_generator_environment_keeps_private_frame_state(self) -> None:
        source = """\
def make() -> str:
    return "left"

def outer():
    def nested(value: str):
        return make() + (yield value)
    return nested("right")
"""
        module, _, _, _ = build_ir_for_single_file2(source.splitlines())
        frame = next(cl for cl in module.classes if cl.has_running_flag)
        assert frame.env_user_function is not None

        insert_spills(frame.env_user_function, frame)

        env_type = frame.attributes[ENV_ATTR_NAME]
        assert isinstance(env_type, RInstance)
        environment = env_type.class_ir

        assert frame.attrs_are_thread_confined()
        assert NEXT_LABEL_ATTR_NAME in frame.attributes
        assert any(name.startswith(TEMP_ATTR_NAME + "2_") for name in frame.attributes)
        assert GENERATOR_ATTRIBUTE_PREFIX + "value" in environment.attributes
