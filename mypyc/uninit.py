"""Insert checks for uninitialized values."""

from typing import List

from mypyc.analysis import (
    get_cfg,
    cleanup_cfg,
    analyze_must_defined_regs,
    AnalysisDict
)
from mypyc.ir.ops import (
    BasicBlock, Branch, Value, RaiseStandardError, Unreachable, Environment, Register
)
from mypyc.ir.func_ir import FuncIR


def insert_uninit_checks(ir: FuncIR) -> None:
    # Remove dead blocks from the CFG, which helps avoid spurious
    # checks due to unused error handling blocks.
    cleanup_cfg(ir.blocks)

    cfg = get_cfg(ir.blocks)
    args = set(reg for reg in ir.env.regs() if ir.env.indexes[reg] < len(ir.args))
    must_defined = analyze_must_defined_regs(ir.blocks, cfg, args, ir.env.regs())

    ir.blocks = split_blocks_at_uninits(ir.env, ir.blocks, must_defined.before)


def split_blocks_at_uninits(env: Environment,
                            blocks: List[BasicBlock],
                            pre_must_defined: 'AnalysisDict[Value]') -> List[BasicBlock]:
    new_blocks = []  # type: List[BasicBlock]

    # First split blocks on ops that may raise.
    for block in blocks:
        ops = block.ops
        block.ops = []
        cur_block = block
        new_blocks.append(cur_block)

        for i, op in enumerate(ops):
            defined = pre_must_defined[block, i]
            for src in op.unique_sources():
                # If a register operand is not guaranteed to be
                # initialized is an operand to something other than a
                # check that it is defined, insert a check.
                if (isinstance(src, Register) and src not in defined
                        and not (isinstance(op, Branch) and op.op == Branch.IS_ERROR)):
                    new_block, error_block = BasicBlock(), BasicBlock()
                    new_block.error_handler = error_block.error_handler = cur_block.error_handler
                    new_blocks += [error_block, new_block]

                    env.vars_needing_init.add(src)

                    cur_block.ops.append(Branch(src,
                                                true_label=error_block,
                                                false_label=new_block,
                                                op=Branch.IS_ERROR,
                                                line=op.line))
                    raise_std = RaiseStandardError(
                        RaiseStandardError.UNBOUND_LOCAL_ERROR,
                        "local variable '{}' referenced before assignment".format(src.name),
                        op.line)
                    env.add_op(raise_std)
                    error_block.ops.append(raise_std)
                    error_block.ops.append(Unreachable())
                    cur_block = new_block
            cur_block.ops.append(op)

    return new_blocks
