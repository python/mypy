"""Tests for promoting generator registers onto their frames."""

from __future__ import annotations

import unittest

from mypyc.common import TEMP_ATTR_NAME
from mypyc.ir.class_ir import ClassIR
from mypyc.ir.ops import GetAttr
from mypyc.test.testutil import build_ir_for_single_file2
from mypyc.transform.generator_spills import registers_live_across_yield


def generator_class(source: str, name: str) -> ClassIR:
    module, _, _, _ = build_ir_for_single_file2(source.splitlines())
    return next(
        cl for cl in module.classes if cl.name == name and cl.env_user_function is not None
    )


class TestGeneratorSpills(unittest.TestCase):
    def test_saved_exception_state_is_promoted(self) -> None:
        cl = generator_class(
            """\
from typing import Iterator

def gen() -> Iterator[int]:
    try:
        yield 1
    finally:
        yield 2
""",
            "gen_gen",
        )
        helper = cl.env_user_function
        assert helper is not None
        slots = {name for name in cl.attributes if name.startswith(TEMP_ATTR_NAME + "3_")}
        assert len(slots) == 1
        reads = [
            op
            for block in helper.blocks
            for op in block.ops
            if isinstance(op, GetAttr) and op.attr in slots
        ]
        assert reads and all(read.allow_error_value for read in reads)
        assert not registers_live_across_yield(helper)

    def test_address_taken_register_is_not_promoted(self) -> None:
        cl = generator_class(
            """\
from typing import Any, Generator

def gen(values: Any) -> Generator[int, None, None]:
    yield from values
""",
            "gen_gen",
        )
        helper = cl.env_user_function
        assert helper is not None
        assert not registers_live_across_yield(helper)
