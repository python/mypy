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
from mypyc.ir.ops import Assign, AssignMulti, LoadErrorValue, Value
from mypyc.irbuild.ll_builder import LowLevelIRBuilder
from mypyc.options import CompilerOptions
from mypyc.sametype import is_same_type
from mypyc.transform.ir_transform import IRTransform


def do_copy_propagation(fn: FuncIR, options: CompilerOptions) -> None:
    """Perform copy propagation optimization for fn."""

    # Anything with an assignment count >1 will not be optimized
    # here, as it would be require data flow analysis and we want to
    # keep this simple & fast, at least until we've made data flow
    # analysis much faster.
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
                # Does this look like a supported assignment?
                # TODO: Something needs LoadErrorValue assignments to be preserved
                if (
                    c == 0
                    and is_same_type(op.dest.type, op.src.type)
                    and not isinstance(op.src, LoadErrorValue)
                ):
                    replacements[op.dest] = op.src
                elif c == 1:
                    replacements.pop(op.dest, 0)
            elif isinstance(op, AssignMulti):
                # Copy propagation not supported for AssignMulti destinations
                counts[op.dest] = 2
                replacements.pop(op.dest, 0)

    # Follow chains of propagation with multiple assignments.
    for src, dst in list(replacements.items()):
        while dst in replacements:
            dst = replacements[dst]
        replacements[src] = dst

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
