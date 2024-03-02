"""Simple copy propagation optimization.

Example input:

    x = f()
    y = x

The register x is redundant and we can directly assign its value to y:

    y = f()

This can optimize away registers that are assigned to once.
"""

from __future__ import annotations

from mypyc.ir.func_ir import FuncIR
from mypyc.ir.ops import Assign, AssignMulti, Value
from mypyc.irbuild.ll_builder import LowLevelIRBuilder
from mypyc.options import CompilerOptions
from mypyc.transform.ir_transform import IRTransform


def do_copy_propagation(fn: FuncIR, options: CompilerOptions) -> None:
    """Perform copy propagation optimization for fn."""
    counts = {}
    replacements: dict[Value, Value] = {}
    for arg in fn.arg_regs:
        # Arguments can't be propagated, so use value >1
        counts[arg] = 2

    for block in fn.blocks:
        for op in block.ops:
            if isinstance(op, Assign):
                c = counts.get(op.dest, 0)
                counts[op.dest] = c + 1
                if c == 0:
                    replacements[op.dest] = op.src
                elif c == 1:
                    del replacements[op.dest]
            elif isinstance(op, AssignMulti):
                # Copy propagation not supported
                counts[op.dest] = 2
                replacements.pop(op.dest, 0)

    b = LowLevelIRBuilder(None, options)
    t = CopyPropagationTransform(b, replacements)
    t.transform_blocks(fn.blocks)
    fn.blocks = b.blocks



class CopyPropagationTransform(IRTransform):
    def __init__(self, builder: LowLevelIRBuilder, m: dict[Value, Value]) -> None:
        super().__init__(builder)
        self.op_map.update(m)
        self.removed = set(m)

    def visit_assign(self, op: Assign) -> Value | None:
        if op.dest in self.removed:
            return None
        return self.add(op)
