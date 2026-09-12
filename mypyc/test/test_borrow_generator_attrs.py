"""Tests for borrowing reads from private generator-frame attributes."""

from __future__ import annotations

import unittest

from mypyc.common import GENERATOR_ATTRIBUTE_PREFIX, TEMP_ATTR_NAME
from mypyc.ir.class_ir import ClassIR
from mypyc.ir.func_ir import FuncDecl, FuncIR, FuncSignature, RuntimeArg
from mypyc.ir.ops import (
    BasicBlock,
    Branch,
    Call,
    DecRef,
    GetAttr,
    Goto,
    IncRef,
    Integer,
    KeepAlive,
    LoadLiteral,
    Op,
    Register,
    Return,
    SetAttr,
)
from mypyc.ir.rtypes import (
    RInstance,
    RTuple,
    RType,
    bit_rprimitive,
    none_rprimitive,
    str_rprimitive,
)
from mypyc.test.testutil import build_ir_for_single_file2
from mypyc.transform.borrow_generator_attrs import borrow_generator_attrs
from mypyc.transform.exceptions import insert_exception_handling
from mypyc.transform.refcount import insert_ref_count_opcodes
from mypyc.transform.spill import insert_spills
from mypyc.transform.uninit import insert_uninit_checks


def return_none() -> Return:
    return Return(Integer(1, none_rprimitive))


class TestBorrowGeneratorAttrs(unittest.TestCase):
    def make_helper(
        self, blocks: list[BasicBlock], attributes: dict[str, RType]
    ) -> tuple[FuncIR, ClassIR, Register]:
        cl = ClassIR("gen", "module", is_generated=True)
        cl.has_private_generator_frame = True
        cl.has_running_flag = True
        cl.attributes.update(attributes)
        self_reg = Register(RInstance(cl), "self", is_arg=True)
        decl = FuncDecl(
            "__mypyc_generator_helper__",
            cl.name,
            cl.module_name,
            FuncSignature([RuntimeArg("self", self_reg.type)], none_rprimitive),
        )
        ir = FuncIR(decl, [self_reg], blocks)
        cl.env_user_function = ir
        return ir, cl, self_reg

    def make_single_block_helper(
        self, body: list[Op], attributes: dict[str, RType] | None = None
    ) -> tuple[FuncIR, ClassIR, Register]:
        block = BasicBlock()
        block.ops = [*body, return_none()]
        return self.make_helper(blocks=[block], attributes=attributes or {"value": str_rprimitive})

    def test_borrows_read_used_in_same_block(self) -> None:
        ir, cl, self_reg = self.make_single_block_helper([])
        read = GetAttr(self_reg, "value", -1)
        ir.blocks[0].ops[:0] = [read, KeepAlive([read])]

        borrow_generator_attrs(ir, cl)

        assert read.is_borrowed

    def test_requires_thread_confined_frame(self) -> None:
        ir, cl, self_reg = self.make_single_block_helper([])
        read = GetAttr(self_reg, "value", -1)
        ir.blocks[0].ops[:0] = [read, KeepAlive([read])]
        cl.has_running_flag = False

        borrow_generator_attrs(ir, cl)

        assert not read.is_borrowed

    def test_same_attribute_store_kills_borrow(self) -> None:
        ir, cl, self_reg = self.make_single_block_helper([])
        read = GetAttr(self_reg, "value", -1)
        replacement = LoadLiteral("new", str_rprimitive)
        ir.blocks[0].ops[:0] = [
            read,
            replacement,
            SetAttr(self_reg, "value", replacement, -1),
            KeepAlive([read]),
        ]

        borrow_generator_attrs(ir, cl)

        assert not read.is_borrowed

    def test_different_attribute_store_does_not_kill_borrow(self) -> None:
        ir, cl, self_reg = self.make_single_block_helper(
            [], {"value": str_rprimitive, "other": str_rprimitive}
        )
        read = GetAttr(self_reg, "value", -1)
        replacement = LoadLiteral("new", str_rprimitive)
        ir.blocks[0].ops[:0] = [
            read,
            replacement,
            SetAttr(self_reg, "other", replacement, -1),
            KeepAlive([read]),
        ]

        borrow_generator_attrs(ir, cl)

        assert read.is_borrowed

    def test_arbitrary_call_does_not_kill_borrow(self) -> None:
        ir, cl, self_reg = self.make_single_block_helper([])
        read = GetAttr(self_reg, "value", -1)
        callee = FuncDecl("callee", None, "module", FuncSignature([], none_rprimitive))
        ir.blocks[0].ops[:0] = [read, Call(callee, [], -1), KeepAlive([read])]

        borrow_generator_attrs(ir, cl)

        assert read.is_borrowed

    def test_passing_frame_to_call_kills_borrow(self) -> None:
        ir, cl, self_reg = self.make_single_block_helper([])
        read = GetAttr(self_reg, "value", -1)
        ir.blocks[0].ops[:0] = [
            read,
            Call(cl.clear_on_completion, [self_reg], -1),
            KeepAlive([read]),
        ]

        borrow_generator_attrs(ir, cl)

        assert not read.is_borrowed

    def test_borrows_across_basic_blocks(self) -> None:
        first = BasicBlock()
        second = BasicBlock()
        ir, cl, self_reg = self.make_helper([first, second], {"value": str_rprimitive})
        read = GetAttr(self_reg, "value", -1)
        first.ops = [read, Goto(second)]
        second.ops = [KeepAlive([read]), return_none()]

        borrow_generator_attrs(ir, cl)

        assert read.is_borrowed

    def test_store_on_one_branch_kills_borrow_at_join(self) -> None:
        entry = BasicBlock()
        store = BasicBlock()
        no_store = BasicBlock()
        join = BasicBlock()
        ir, cl, self_reg = self.make_helper(
            [entry, store, no_store, join], {"value": str_rprimitive}
        )
        read = GetAttr(self_reg, "value", -1)
        replacement = LoadLiteral("new", str_rprimitive)
        entry.ops = [read, Branch(Integer(1, bit_rprimitive), store, no_store, Branch.BOOL)]
        store.ops = [replacement, SetAttr(self_reg, "value", replacement, -1), Goto(join)]
        no_store.ops = [Goto(join)]
        join.ops = [KeepAlive([read]), return_none()]

        borrow_generator_attrs(ir, cl)

        assert not read.is_borrowed

    def test_suspension_kills_borrow(self) -> None:
        entry = BasicBlock()
        before_yield = BasicBlock()
        continuation = BasicBlock()
        ir, cl, self_reg = self.make_helper(
            [entry, before_yield, continuation], {"value": str_rprimitive}
        )
        read = GetAttr(self_reg, "value", -1)
        entry.ops = [
            Branch(Integer(1, bit_rprimitive), before_yield, continuation, Branch.BOOL)
        ]
        before_yield.ops = [
            read,
            Return(Integer(1, none_rprimitive), yield_target=continuation),
        ]
        continuation.ops = [KeepAlive([read]), return_none()]

        borrow_generator_attrs(ir, cl)

        assert not read.is_borrowed
        read.is_borrowed = True
        with self.assertRaisesRegex(AssertionError, "cannot spill borrowed attribute read"):
            insert_spills(ir, cl)

    def test_borrows_nullable_rtuple_attribute(self) -> None:
        tuple_type = RTuple([str_rprimitive, str_rprimitive])
        ir, cl, self_reg = self.make_single_block_helper([], {"value": tuple_type})
        read = GetAttr(self_reg, "value", -1, allow_error_value=True)
        ir.blocks[0].ops[:0] = [read, KeepAlive([read])]

        borrow_generator_attrs(ir, cl)

        assert read.is_borrowed

    def test_skips_read_that_all_consumers_steal(self) -> None:
        ir, cl, self_reg = self.make_single_block_helper(
            [], {"value": str_rprimitive, "other": str_rprimitive}
        )
        read = GetAttr(self_reg, "value", -1)
        ir.blocks[0].ops[:0] = [read, SetAttr(self_reg, "other", read, -1)]

        borrow_generator_attrs(ir, cl)

        assert not read.is_borrowed

    def test_borrows_private_frame_but_not_separate_environment(self) -> None:
        source = """\
from typing import Generator

def use(value: str) -> str:
    return value

def gen(value: str) -> Generator[str, None, str]:
    other = value
    def nested() -> str:
        return value
    yield use(other)
    return use(other)
"""
        module, _, _, _ = build_ir_for_single_file2(source.splitlines())
        cl = next(cl for cl in module.classes if cl.name == "gen_gen")
        ir = cl.env_user_function
        assert ir is not None
        insert_uninit_checks(ir, True)
        insert_exception_handling(ir, True)

        borrow_generator_attrs(ir, cl)

        reads = [op for block in ir.blocks for op in block.ops if isinstance(op, GetAttr)]
        private_reads = [
            op
            for op in reads
            if op.obj is ir.arg_regs[0] and op.attr == GENERATOR_ATTRIBUTE_PREFIX + "other"
        ]
        shared_reads = [
            op
            for op in reads
            if op.obj is not ir.arg_regs[0] and op.attr == GENERATOR_ATTRIBUTE_PREFIX + "value"
        ]
        assert private_reads and all(op.is_borrowed for op in private_reads)
        assert shared_reads and not any(op.is_borrowed for op in shared_reads)

    def test_borrows_promoted_saved_exception_state(self) -> None:
        source = """\
from typing import Iterator

def gen() -> Iterator[int]:
    try:
        yield 1
    finally:
        yield 2
"""
        module, _, _, _ = build_ir_for_single_file2(source.splitlines())
        cl = next(cl for cl in module.classes if cl.name == "gen_gen")
        ir = cl.env_user_function
        assert ir is not None
        slots = {name for name in cl.attributes if name.startswith(TEMP_ATTR_NAME + "3_")}
        insert_uninit_checks(ir, True)
        insert_exception_handling(ir, True)

        borrow_generator_attrs(ir, cl)

        reads = [
            op
            for block in ir.blocks
            for op in block.ops
            if isinstance(op, GetAttr) and op.attr in slots
        ]
        assert reads and all(op.allow_error_value and op.is_borrowed for op in reads)
        insert_ref_count_opcodes(ir)
        assert not any(
            isinstance(op, IncRef | DecRef) and op.src in reads
            for block in ir.blocks
            for op in block.ops
        )
        insert_spills(ir, cl)
