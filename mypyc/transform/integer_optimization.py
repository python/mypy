from typing import List, Dict

from mypyc.ir.ops import BasicBlock, LoadInt, Assign
from mypyc.ir.rtypes import is_short_int_rprimitive, is_int_rprimitive


def find_constant_integer_registers(blocks: List[BasicBlock],
                                    convert_tagged: bool = False) -> Dict[str, int]:
    """
    Find all registers with constant integer values.

    Returns a mapping from register names to int values
    """
    const_int_regs = {}  # type: Dict[str, int]
    for block in blocks:
        for op in block.ops:
            # Case 1: All LoadInt are constant int registers
            if isinstance(op, LoadInt) and op.name not in const_int_regs:
                if convert_tagged and (is_short_int_rprimitive(op.type)
                                       or is_int_rprimitive(op.type)):
                    const_int_regs[op.name] = op.value * 2
                else:
                    const_int_regs[op.name] = op.value
            # Case 2: For each assign operation, if the src is a known constant,
            #         then the dest is a constant
            if isinstance(op, Assign):
                dest = op.dest
                src = op.src
                # if we already encounter dest before, it means
                # it's conditionally assigned, so we simply remove it
                if dest.name in const_int_regs:
                    del const_int_regs[dest.name]
                    continue
                if src.name in const_int_regs:
                    const_int_regs[dest.name] = const_int_regs[src.name]
            # TODO: should we compute BinaryIntOp with two const operands during this pass
            #       and store its value as well?
    return const_int_regs
