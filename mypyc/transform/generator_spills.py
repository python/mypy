"""Move generator registers that survive suspension onto the generator frame."""

from __future__ import annotations

from mypyc.analysis.dataflow import analyze_live_regs_with_exception_edges, cleanup_cfg
from mypyc.common import TEMP_ATTR_NAME, generator_frame_attribute_prefix
from mypyc.ir.class_ir import ClassIR
from mypyc.ir.func_ir import FuncIR
from mypyc.ir.ops import (
    NO_TRACEBACK_LINE_NO,
    Assign,
    AssignMulti,
    BaseAssign,
    BasicBlock,
    Branch,
    GetAttr,
    LoadAddress,
    LoadErrorValue,
    Op,
    Register,
    SetAttr,
    Value,
)
from mypyc.namegen import exported_name


def promote_generator_registers(ir: FuncIR, frame: ClassIR) -> None:
    """Replace registers live across a suspension with frame attributes.

    This runs before uninitialized-value, exception, and refcount transforms.
    """
    cleanup_cfg(ir.blocks)
    registers = registers_live_across_yield(ir)
    if not registers:
        return

    nullable = nullable_registers(ir.blocks)
    slots = allocate_slots(frame, registers)
    rewrite_registers(ir.blocks, ir.arg_regs[0], slots, nullable)

    # Keep this close to the rewrite: it catches a new op kind that is not
    # handled above without restating the liveness analysis.
    for block in ir.blocks:
        for op in block.ops:
            assert not any(source in slots for source in op.sources())
            assert not (isinstance(op, BaseAssign) and op.dest in slots)


def registers_live_across_yield(ir: FuncIR) -> list[Register]:
    """Return promotable registers live at generator-helper entry."""
    live_in = analyze_live_regs_with_exception_edges(ir.blocks)
    excluded = unpromotable_registers(ir.blocks)
    registers = [
        value
        for value in live_in[ir.blocks[0]]
        if isinstance(value, Register) and not value.is_arg and value not in excluded
    ]
    return order_registers(registers, ir.blocks)


def unpromotable_registers(blocks: list[BasicBlock]) -> set[Register]:
    """Find registers whose representation requires a real C local."""
    result: set[Register] = set()
    for block in blocks:
        for op in block.ops:
            if isinstance(op, LoadAddress) and isinstance(op.src, Register):
                result.add(op.src)
            elif isinstance(op, AssignMulti):
                result.add(op.dest)
            elif (
                isinstance(op, Assign)
                and isinstance(op.src, LoadErrorValue)
                and op.src.undefines
                and op.dest.type.error_overlap
            ):
                result.add(op.dest)
    return result


def nullable_registers(blocks: list[BasicBlock]) -> set[Register]:
    """Find registers for which the error value is an ordinary state."""
    result: set[Register] = set()
    for block in blocks:
        for op in block.ops:
            if (
                isinstance(op, Branch)
                and op.op == Branch.IS_ERROR
                and isinstance(op.value, Register)
            ):
                result.add(op.value)
            elif (
                isinstance(op, Assign)
                and isinstance(op.src, LoadErrorValue)
                and not op.src.undefines
            ):
                result.add(op.dest)
    return result


def order_registers(registers: list[Register], blocks: list[BasicBlock]) -> list[Register]:
    """Order registers by first appearance for deterministic frame layouts."""
    positions: dict[Register, int] = {}
    for block in blocks:
        for op in block.ops:
            values = op.sources()
            if isinstance(op, BaseAssign):
                values = [op.dest, *values]
            for value in values:
                if isinstance(value, Register) and value not in positions:
                    positions[value] = len(positions)
    return sorted(registers, key=positions.__getitem__)


def allocate_slots(frame: ClassIR, registers: list[Register]) -> dict[Register, str]:
    slots: dict[Register, str] = {}
    owner = exported_name(frame.fullname)
    source_prefix = generator_frame_attribute_prefix(frame.fullname)
    for index, register in enumerate(registers):
        if register.name:
            name = available_attr_name(frame, source_prefix + register.name)
        else:
            name = f"{TEMP_ATTR_NAME}3_{owner}_{index}"
            if register.type.error_overlap:
                # Compiler temporaries are assigned before use. Recording a
                # default avoids allocating an undefinedness bitmap for them.
                frame.attrs_with_defaults.add(name)
        frame.attributes[name] = register.type
        slots[register] = name
    return slots


def available_attr_name(frame: ClassIR, base: str) -> str:
    if not frame.has_attr(base):
        return base
    suffix = 2
    while frame.has_attr(f"{base}__{suffix}"):
        suffix += 1
    return f"{base}__{suffix}"


def rewrite_registers(
    blocks: list[BasicBlock],
    frame_reg: Register,
    slots: dict[Register, str],
    nullable: set[Register],
) -> None:
    """Replace promoted register accesses with generator frame attribute accesses."""
    # IRTransform maps each value to one replacement, but mutable registers need a fresh
    # attribute read at each use, so we can't use IRTransform here.
    for block in blocks:
        old_ops = block.ops
        block.ops = []
        for op in old_ops:
            replacements: dict[Register, GetAttr] = {}
            new_sources: list[Value] = []
            for source in op.sources():
                if isinstance(source, Register) and source in slots:
                    read = replacements.get(source)
                    if read is None:
                        read = GetAttr(
                            frame_reg,
                            slots[source],
                            source_line(op, source),
                            allow_error_value=source in nullable,
                        )
                        block.ops.append(read)
                        replacements[source] = read
                    new_sources.append(read)
                else:
                    new_sources.append(source)
            op.set_sources(new_sources)

            if isinstance(op, Assign) and op.dest in slots:
                block.ops.append(
                    SetAttr(frame_reg, slots[op.dest], op.src, source_line(op, op.dest))
                )
            else:
                block.ops.append(op)


def source_line(op: Op, register: Register) -> int:
    if op.line >= 0 or op.line == NO_TRACEBACK_LINE_NO:
        return op.line
    if register.line >= 0:
        return register.line
    return NO_TRACEBACK_LINE_NO
