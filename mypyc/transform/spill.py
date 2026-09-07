"""Insert spills for values that are live across yields."""

from __future__ import annotations

from collections.abc import Collection
from typing import cast

from mypyc.analysis.dataflow import AnalysisResult, analyze_live_regs, get_cfg
from mypyc.common import TEMP_ATTR_NAME
from mypyc.ir.class_ir import ClassIR
from mypyc.ir.func_ir import FuncIR
from mypyc.ir.ops import (
    BasicBlock,
    Branch,
    DecRef,
    GetAttr,
    IncRef,
    LoadErrorValue,
    Op,
    Register,
    SetAttr,
    Value,
)
from mypyc.namegen import exported_name


def insert_spills(ir: FuncIR, frame: ClassIR) -> None:
    cfg = get_cfg(ir.blocks, use_yields=True)
    live = analyze_live_regs(ir.blocks, cfg)
    entry_live = live.before[ir.blocks[0], 0]

    entry_live = {op for op in entry_live if not (isinstance(op, Register) and op.is_arg)}
    # TODO: Actually for now, no Registers at all -- we keep the manual spills
    entry_live = {op for op in entry_live if not isinstance(op, Register)}

    ir.blocks = spill_regs(ir.blocks, frame, entry_live, live, ir.arg_regs[0])


def sort_values(values: Collection[Op], blocks: list[BasicBlock]) -> list[Op]:
    if len(values) > 1:
        order = {}
        i = 0
        for block in blocks:
            for op in block.ops:
                order[op] = i
                i += 1
        return sorted(values, key=lambda v: order[v])
    else:
        return list(values)


def spill_regs(
    blocks: list[BasicBlock],
    frame: ClassIR,
    to_spill: set[Value],
    live: AnalysisResult[Value],
    frame_reg: Register,
) -> list[BasicBlock]:
    spill_locs = {}
    # Sort values to make the order deterministic. All the spilled values are
    # known to be Op instances, so the cast is safe.
    for i, val in enumerate(sort_values(cast(set[Op], to_spill), blocks)):
        # Generator classes for overriding methods can inherit from one another. Include the
        # module-qualified owning class name so unrelated helper spills don't alias an inherited
        # struct field.
        name = f"{TEMP_ATTR_NAME}2_{exported_name(frame.fullname)}_{i}"
        frame.attributes[name] = val.type
        if val.type.error_overlap:
            # We can safely treat as always initialized, since the type has no pointers.
            # This way we also don't need to manage the defined attribute bitfield.
            frame._always_initialized_attrs.add(name)
        spill_locs[val] = name

    for block in blocks:
        ops = block.ops
        block.ops = []

        for i, op in enumerate(ops):
            to_decref = []

            if isinstance(op, IncRef) and op.src in spill_locs:
                raise AssertionError("not sure what to do with an incref of a spill...")
            if isinstance(op, DecRef) and op.src in spill_locs:
                # When we decref a spilled value, we turn that into
                # NULLing out the attribute, but only if the spilled
                # value is not live *when we include yields in the
                # CFG*. (The original decrefs are computed without that.)
                #
                # We also skip a decref if the frame register is not
                # live. That should only happen when an exception is
                # being raised, so everything should be handled there.
                if op.src not in live.after[block, i] and frame_reg in live.after[block, i]:
                    # Skip the DecRef but null out the spilled location
                    null = LoadErrorValue(op.src.type)
                    block.ops.extend([null, SetAttr(frame_reg, spill_locs[op.src], null, op.line)])
                continue

            if (
                any(src in spill_locs for src in op.sources())
                # N.B: IS_ERROR should be before a spill happens
                # XXX: but could we have a regular branch?
                and not (isinstance(op, Branch) and op.op == Branch.IS_ERROR)
            ):
                new_sources: list[Value] = []
                stolen = op.stolen()
                for src in op.sources():
                    if src in spill_locs:
                        read = GetAttr(frame_reg, spill_locs[src], op.line)
                        block.ops.append(read)
                        new_sources.append(read)
                        if src.type.is_refcounted and src not in stolen:
                            to_decref.append(read)
                    else:
                        new_sources.append(src)

                op.set_sources(new_sources)

            block.ops.append(op)

            for dec in to_decref:
                block.ops.append(DecRef(dec))

            if op in spill_locs:
                # XXX: could we set uninit?
                block.ops.append(SetAttr(frame_reg, spill_locs[op], op, op.line))

    return blocks
