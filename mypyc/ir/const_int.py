from typing import List, Dict

from mypyc.ir.ops import BasicBlock, LoadInt


def find_constant_integer_registers(blocks: List[BasicBlock]) -> Dict[LoadInt, int]:
    """Find all registers with constant integer values."""
    const_int_regs = {}  # type: Dict[LoadInt, int]
    for block in blocks:
        for op in block.ops:
            if isinstance(op, LoadInt):
                const_int_regs[op] = op.value
    return const_int_regs
