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
        # A nested generator needs a separate environment. Since make() is
        # evaluated before the yield, its result must be spilled across the
        # suspension point by the post-IRBuild spill pass.
        source = """\
def make() -> str:
    return "left"

def outer():
    def nested(value: str):
        for item in [value]:
            # The loop iterator uses IR-builder-managed spill slots, while the
            # result of make() is spilled later by the spill transform.
            return make() + (yield item)
        return "unreachable"
    return nested("right")
"""
        module, _, _, _ = build_ir_for_single_file2(source.splitlines())
        frame = next(cl for cl in module.classes if cl.has_running_flag)
        assert frame.env_user_function is not None

        insert_spills(frame.env_user_function, frame)

        env_type = frame.attributes[ENV_ATTR_NAME]
        assert isinstance(env_type, RInstance)
        environment = env_type.class_ir

        # Private generator resume state lives on the generator frame, which
        # is protected by the running flag and can use plain attribute access.
        assert frame.attrs_are_thread_confined()
        assert NEXT_LABEL_ATTR_NAME in frame.attributes
        assert any(name.startswith(TEMP_ATTR_NAME + "1_") for name in frame.attributes)
        assert any(name.startswith(TEMP_ATTR_NAME + "2_") for name in frame.attributes)

        # Source-level variables stay in the shared environment.
        assert GENERATOR_ATTRIBUTE_PREFIX + "value" in environment.attributes
