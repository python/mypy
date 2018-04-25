"""Transformation for inserting refrecence count inc/dec opcodes.

This transformation happens towards the end of compilation. Before this
transformation, reference count management is not explicitly handled at all.
By postponing this pass, the previous passes are simpler as they don't have
to update reference count opcodes.

The approach is to decrement reference counts soon after a value is no
longer live, to quickly free memory (and call __del__ methods), though
there are no strict guarantees -- other than that local variables are
freed before return from a function.

Function arguments are a little special. They are initially considered
'borrowed' from the caller and their reference counts don't need to be
decremented before returning. An assignment to a borrowed value turns it
into a regular, owned reference that needs to freed before return.
"""

from typing import List, Dict, Tuple, Set, Iterable, Optional

from mypyc.analysis import (
    get_cfg,
    analyze_must_defined_regs,
    analyze_live_regs,
    analyze_borrowed_arguments,
    AnalysisDict
)
from mypyc.ops import (
    FuncIR, BasicBlock, Assign, RegisterOp, DecRef, IncRef, Branch, Goto, Environment,
    Return, Op, Register, Label, Cast, Box, Unbox, PrimitiveOp, LoadStatic,
)


def insert_ref_count_opcodes(ir: FuncIR) -> None:
    """Insert reference count inc/dec opcodes to a function.

    This is the entry point to this module.
    """
    cfg = get_cfg(ir.blocks)
    args = set([Register(i) for i in range(len(ir.args))])
    live = analyze_live_regs(ir.blocks, cfg)
    borrow = analyze_borrowed_arguments(ir.blocks, cfg, args)
    for block in ir.blocks[:]:
        if isinstance(block.ops[-1], (Branch, Goto)):
            insert_branch_inc_and_decrefs(block,
                                          ir.blocks,
                                          live.before,
                                          borrow.before,
                                          borrow.after,
                                          ir.env)
        transform_block(block, live.before, live.after, borrow.before, ir.env)


def transform_block(block: BasicBlock,
                    pre_live: AnalysisDict[Register],
                    post_live: AnalysisDict[Register],
                    pre_borrow: AnalysisDict[Register],
                    env: Environment) -> None:
    old_ops = block.ops
    ops = []  # type: List[Op]
    for i, op in enumerate(old_ops):
        key = (block.label, i)
        if isinstance(op, (Assign, Cast, Box)):
            # These operations just copy/steal a reference and don't create new
            # references.
            if op.src in post_live[key] or op.src in pre_borrow[key]:
                ops.append(IncRef(op.src, env.types[op.src]))
                if (op.dest not in pre_borrow[key] and
                        op.dest in pre_live[key]):
                    ops.append(DecRef(op.dest, env.types[op.dest]))
            ops.append(op)
            if op.dest not in post_live[key]:
                ops.append(DecRef(op.dest, env.types[op.dest]))
        elif isinstance(op, RegisterOp):
            # These operations construct a new reference.
            tmp_reg = None  # type: Optional[Register]
            if (op.dest not in pre_borrow[key] and
                    op.dest in pre_live[key]):
                if op.dest not in op.sources():
                    ops.append(DecRef(op.dest, env.types[op.dest]))
                else:
                    tmp_reg = env.add_temp(env.types[op.dest])
                    ops.append(Assign(tmp_reg, op.dest))
            ops.append(op)
            for src in op.unique_sources():
                # Decrement source that won't be live afterwards.
                if src not in post_live[key] and src not in pre_borrow[key]:
                    if src != op.dest:
                        ops.append(DecRef(src, env.types[src]))
            # TODO: Analyze LoadStatics as being borrowed! (#66)
            if isinstance(op, LoadStatic):
                ops.append(IncRef(op.dest, env.types[op.dest]))
            if op.dest is not None and op.dest not in post_live[key]:
                ops.append(DecRef(op.dest, env.types[op.dest]))
            if tmp_reg is not None:
                ops.append(DecRef(tmp_reg, env.types[tmp_reg]))
        elif isinstance(op, Return) and op.reg in pre_borrow[key]:
            # The return op returns a new reference.
            ops.append(IncRef(op.reg, env.types[op.reg]))
            ops.append(op)
        else:
            ops.append(op)
    block.ops = ops


def insert_branch_inc_and_decrefs(
        block: BasicBlock,
        blocks: List[BasicBlock],
        pre_live: AnalysisDict,
        pre_borrow: AnalysisDict,
        post_borrow: AnalysisDict,
        env: Environment) -> None:
    """Insert inc_refs and/or dec_refs after a branch/goto.

    Add dec_refs for registers that become dead after a branch.
    Add inc_refs for registers that become unborrowed after a branch or goto.

    Branches are special as the true and false targets may have a different
    live and borrowed register sets. Add new blocks before the true/false target
    blocks that tweak reference counts.

    Example where we need to add an inc_ref:

      def f(a: int) -> None
          if a:
              a = 1
          return a  # a is borrowed if condition is false and unborrowed if true
    """
    prev_key = (block.label, len(block.ops) - 1)
    source_live_regs = pre_live[prev_key]
    source_borrowed = post_borrow[prev_key]
    if isinstance(block.ops[-1], Branch):
        branch = block.ops[-1]

        true_opcodes = (
            after_branch_decrefs(
                branch.true, pre_live, source_borrowed, source_live_regs, env) +
            after_branch_increfs(
                branch.true, pre_borrow, source_borrowed, env))
        if true_opcodes:
            branch.true = add_block(true_opcodes, blocks, branch.true)

        false_opcodes = (
            after_branch_decrefs(
                branch.false, pre_live, source_borrowed, source_live_regs, env) +
            after_branch_increfs(
                branch.false, pre_borrow, source_borrowed, env))
        if false_opcodes:
            branch.false = add_block(false_opcodes, blocks, branch.false)
    elif isinstance(block.ops[-1], Goto):
        goto = block.ops[-1]
        new_opcodes = after_branch_increfs(
            goto.label, pre_borrow, source_borrowed, env)
        if new_opcodes:
            goto.label = add_block(new_opcodes, blocks, goto.label)


def after_branch_decrefs(label: Label,
                         pre_live: AnalysisDict,
                         source_borrowed: Set[Register],
                         source_live_regs: Set[Register],
                         env: Environment) -> List[Op]:
    target_pre_live = pre_live[label, 0]
    decref = source_live_regs - target_pre_live - source_borrowed
    if decref:
        return [DecRef(reg, env.types[reg]) for reg in sorted(decref)]
    return []


def after_branch_increfs(label: Label,
                         pre_borrow: AnalysisDict,
                         source_borrowed: Set[Register],
                         env: Environment) -> List[Op]:
    target_borrowed = pre_borrow[label, 0]
    incref = source_borrowed - target_borrowed
    if incref:
        return [IncRef(reg, env.types[reg]) for reg in sorted(incref)]
    return []


def add_block(ops: Iterable[Op], blocks: List[BasicBlock], label: Label) -> Label:
    block = BasicBlock(Label(len(blocks)))
    block.ops.extend(ops)
    block.ops.append(Goto(label))
    blocks.append(block)
    return block.label
