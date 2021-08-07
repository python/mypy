from typing import List, Set, Tuple

from mypyc.ir.ops import (
    OpVisitor, Register, Goto, Assign, AssignMulti, SetMem, Call, MethodCall, LoadErrorValue,
    LoadLiteral, GetAttr, SetAttr, LoadStatic, InitStatic, TupleGet, TupleSet, Box, Unbox,
    Cast, RaiseStandardError, CallC, Truncate, LoadGlobal, IntOp, ComparisonOp, LoadMem,
    GetElementPtr, LoadAddress, KeepAlive, RegisterOp, BasicBlock
)
from mypyc.analysis.dataflow import BaseAnalysisVisitor, AnalysisResult

GenAndKill = Tuple[Set[str], Set[str]]


class AttributeMaybeDefinedVisitor(BaseAnalysisVisitor[str]):
    def __init__(self, self_reg: Register) -> None:
        self.self_reg = self_reg

    def visit_register_op(self, op: RegisterOp) -> Tuple[Set[str], Set[str]]:
        if isinstance(op, SetAttr) and op.obj is self.self_reg:
            return {op.attr}, set()
        return set(), set()

    def visit_assign(self, op: Assign) -> Tuple[Set[str], Set[str]]:
        return set(), set()

    def visit_assign_multi(self, op: AssignMulti) -> Tuple[Set[str], Set[str]]:
        return set(), set()

    def visit_set_mem(self, op: SetMem) -> Tuple[Set[str], Set[str]]:
        return set(), set()


class AttributeMaybeUndefinedVisitor(BaseAnalysisVisitor[str]):
    def __init__(self, self_reg: Register) -> None:
        self.self_reg = self_reg

    def visit_register_op(self, op: RegisterOp) -> Tuple[Set[str], Set[str]]:
        if isinstance(op, SetAttr) and op.obj is self.self_reg:
            return set(), {op.attr}
        return set(), set()

    def visit_assign(self, op: Assign) -> Tuple[Set[str], Set[str]]:
        return set(), set()

    def visit_assign_multi(self, op: AssignMulti) -> Tuple[Set[str], Set[str]]:
        return set(), set()

    def visit_set_mem(self, op: SetMem) -> Tuple[Set[str], Set[str]]:
        return set(), set()


def find_always_defined_attributes(blocks: List[BasicBlock],
                                   all_attrs: Set[str],
                                   maybe_defined: AnalysisResult[str],
                                   maybe_undefined: AnalysisResult[str],
                                   dirty: AnalysisResult[None]) -> Set[str]:
    attrs = all_attrs.copy()
    for block in blocks:
        for i in range(len(block.ops)):
            if (block, i) in dirty.after:
                if (block, i) not in dirty.before:
                    attrs = attrs & (maybe_defined.before[block, i] -
                                     maybe_undefined.before[block, i])
                break
    return attrs


def mark_attr_initialiation_ops(blocks: List[BasicBlock],
                                maybe_defined: AnalysisResult[str],
                                dirty: AnalysisResult[None]) -> None:
    for block in blocks:
        for i, op in enumerate(block.ops):
            if isinstance(op, SetAttr):
                attr = op.attr
                if attr not in maybe_defined.before[block, i] and not dirty.after[block, i]:
                    op.mark_as_initializer()
