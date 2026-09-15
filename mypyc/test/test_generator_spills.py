"""Tests for promoting generator registers onto their frames.

These don't use the normal data-driven tests, since generators produce very verbose IR.
"""

from __future__ import annotations

import unittest

from mypyc.common import (
    ENV_ATTR_NAME,
    GENERATOR_ATTRIBUTE_PREFIX,
    GENERATOR_FRAME_ATTRIBUTE_PREFIX,
    NEXT_LABEL_ATTR_NAME,
    SELF_NAME,
    TEMP_ATTR_NAME,
    generator_frame_attribute_prefix,
)
from mypyc.ir.class_ir import ClassIR
from mypyc.ir.ops import Assign, GetAttr
from mypyc.ir.rtypes import RInstance
from mypyc.test.testutil import build_ir_for_single_file2
from mypyc.transform.generator_spills import registers_live_across_yield


def generator_class(source: str, name: str) -> ClassIR:
    module, _, _, _ = build_ir_for_single_file2(source.splitlines())
    matches = [
        cl
        for cl in module.classes
        if (cl.name == name or cl.name.startswith(name + "___"))
        and cl.env_user_function is not None
    ]
    assert len(matches) == 1
    return matches[0]


def promoted_slots(cl: ClassIR) -> set[str]:
    return {name for name in cl.attributes if name.startswith(TEMP_ATTR_NAME + "3_")}


def frame_variables(cl: ClassIR) -> set[str]:
    prefix = generator_frame_attribute_prefix(cl.fullname, is_final_class=cl.is_final_class)
    return {name.removeprefix(prefix) for name in cl.attributes if name.startswith(prefix)}


class TestGeneratorSpills(unittest.TestCase):
    def test_generator_environment_excludes_helper_arguments(self) -> None:
        # Loading the outer environment must not add the generator helper's arguments or
        # state to the environment class, or overwrite the type of its self-reference.
        module, _, _, _ = build_ir_for_single_file2("""\
from typing import Iterator

def outer() -> Iterator[str]:
    captured = "value"
    def nested() -> str:
        return captured
    yield nested()
""".splitlines())
        frame = next(cl for cl in module.classes if cl.has_running_flag)
        env_type = frame.attributes[ENV_ATTR_NAME]
        assert isinstance(env_type, RInstance)
        environment = env_type.class_ir

        self_type = environment.attributes[SELF_NAME]
        assert isinstance(self_type, RInstance)
        assert self_type.class_ir is environment
        for name in ("type", "value", "traceback", "arg", "stop_iter_ptr", NEXT_LABEL_ATTR_NAME):
            assert name not in environment.attributes

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
        slots = promoted_slots(cl)
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

    def test_loop_state_only_crossing_a_yield_uses_a_slot(self) -> None:
        source = """\
from typing import Iterator

def before_yield(values: list[int]) -> Iterator[int]:
    total = 0
    for value in values:
        total += value
    yield total

def inside_loop(values: list[int]) -> Iterator[int]:
    for value in values:
        yield value
"""
        before = generator_class(source, "before_yield_gen")
        inside = generator_class(source, "inside_loop_gen")
        before_slots = promoted_slots(before)
        inside_slots = promoted_slots(inside)
        assert not before_slots
        assert len(inside_slots) == 1

    def test_return_value_is_copied_before_frame_cleanup(self) -> None:
        cl = generator_class(
            """\
from typing import Any

async def collect(values: Any) -> Any:
    return {value: value async for value in values}
""",
            "collect_gen",
        )
        helper = cl.env_user_function
        assert helper is not None
        result_copies = [
            op
            for block in helper.blocks
            for op in block.ops
            if isinstance(op, Assign) and not op.dest.is_arg
        ]
        assert result_copies

    def test_only_crossing_named_local_is_on_frame(self) -> None:
        cl = generator_class(
            """\
from typing import Generator

def gen() -> Generator[int, None, int]:
    local = 1
    crossing = 2
    yield local
    return crossing
""",
            "gen_gen",
        )
        assert cl.is_final_class
        assert GENERATOR_FRAME_ATTRIBUTE_PREFIX + "crossing" in cl.attributes
        variables = frame_variables(cl)
        assert "crossing" in variables
        assert "local" not in variables

    def test_captured_local_stays_in_environment(self) -> None:
        module, _, _, _ = build_ir_for_single_file2("""\
from typing import Any, Iterator

def gen() -> Iterator[Any]:
    captured = "value"
    def get() -> str:
        return captured
    yield get
""".splitlines())
        frame = next(cl for cl in module.classes if cl.name == "gen_gen")
        environment = next(
            cl for cl in module.classes if GENERATOR_ATTRIBUTE_PREFIX + "captured" in cl.attributes
        )
        assert environment is not frame

    def test_nested_finally_promotes_each_saved_exception(self) -> None:
        cl = generator_class(
            """\
from typing import Iterator

def gen() -> Iterator[int]:
    try:
        try:
            yield 1
        finally:
            yield 2
    finally:
        yield 3
""",
            "gen_gen",
        )
        helper = cl.env_user_function
        assert helper is not None
        slots = promoted_slots(cl)
        assert len(slots) == 2
        assert not registers_live_across_yield(helper)

    def test_recursive_generator_reference_is_rematerialized(self) -> None:
        cl = generator_class(
            """\
from typing import Any, Iterator

def outer(edges: list[list[int]]) -> Any:
    def walk(node: int) -> Iterator[int]:
        for child in edges[node]:
            yield from walk(child)
        yield node
    return walk
""",
            "walk_gen",
        )
        # The recursive reference comes from the closure again on every resume,
        # so it doesn't need a second copy on the generator frame.
        assert "walk" not in frame_variables(cl)
