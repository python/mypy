"""Borrow reads from private generator-frame attributes."""

from __future__ import annotations

from collections.abc import Set as AbstractSet

from mypyc.analysis.dataflow import MUST_ANALYSIS, BaseAnalysisVisitor, get_cfg, run_analysis
from mypyc.ir.class_ir import ClassIR
from mypyc.ir.func_ir import FuncIR
from mypyc.ir.ops import (
    Assign,
    AssignMulti,
    BasicBlock,
    Branch,
    GetAttr,
    KeepAlive,
    Op,
    RegisterOp,
    Return,
    SetAttr,
    SetMem,
    Unreachable,
    Value,
)
from mypyc.ir.rtypes import RInstance

GenAndKill = tuple[AbstractSet[GetAttr], AbstractSet[GetAttr]]
EMPTY: GenAndKill = (frozenset(), frozenset())


class BorrowGeneratorAttrsVisitor(BaseAnalysisVisitor[GetAttr]):
    def __init__(
        self,
        self_reg: Value,
        candidates: set[GetAttr],
        candidates_by_attr: dict[str, set[GetAttr]],
    ) -> None:
        self.self_reg = self_reg
        self.candidates = candidates
        self.candidates_by_attr = candidates_by_attr

    def visit_branch(self, op: Branch) -> GenAndKill:
        return self.visit_sources(op)

    def visit_return(self, op: Return) -> GenAndKill:
        if op.yield_target is not None:
            return frozenset(), self.candidates
        return self.visit_sources(op)

    def visit_unreachable(self, op: Unreachable) -> GenAndKill:
        return EMPTY

    def visit_register_op(self, op: RegisterOp) -> GenAndKill:
        return self.visit_sources(op)

    def visit_assign(self, op: Assign) -> GenAndKill:
        return self.visit_sources(op)

    def visit_assign_multi(self, op: AssignMulti) -> GenAndKill:
        return self.visit_sources(op)

    def visit_set_mem(self, op: SetMem) -> GenAndKill:
        return self.visit_sources(op)

    def visit_get_attr(self, op: GetAttr) -> GenAndKill:
        if op in self.candidates:
            return {op}, frozenset()
        return EMPTY

    def visit_set_attr(self, op: SetAttr) -> GenAndKill:
        if op.obj is self.self_reg:
            return frozenset(), self.candidates_by_attr.get(op.attr, frozenset())
        return EMPTY

    def visit_keep_alive(self, op: KeepAlive) -> GenAndKill:
        return EMPTY

    def visit_sources(self, op: Op) -> GenAndKill:
        if any(source is self.self_reg for source in op.sources()):
            return frozenset(), self.candidates
        return EMPTY


def borrow_generator_attrs(ir: FuncIR, cl: ClassIR) -> None:
    """Mark safe reads from a private generator frame as borrowed.

    The generator running flag prevents external writes while the helper is executing.
    A read can therefore stay borrowed until this helper writes the same attribute or
    passes the frame to an operation that may access it.
    """
    if not cl.attrs_are_thread_confined() or cl.env_user_function is not ir or not ir.arg_regs:
        return

    self_reg = ir.arg_regs[0]
    if not isinstance(self_reg.type, RInstance) or self_reg.type.class_ir is not cl:
        return

    candidates = {
        op
        for block in ir.blocks
        for op in block.ops
        if isinstance(op, GetAttr)
        and op.obj is self_reg
        and op.attr in cl.attributes
        and cl.attr_type(op.attr).is_refcounted
        and not op.is_borrowed
    }
    if not candidates:
        return

    use_positions: dict[GetAttr, list[tuple[BasicBlock, int]]] = {
        candidate: [] for candidate in candidates
    }
    only_stolen = set(candidates)
    for block in ir.blocks:
        for index, op in enumerate(block.ops):
            stolen = op.stolen()
            for source in op.unique_sources():
                if source in candidates:
                    use_positions[source].append((block, index))
                    if source not in stolen:
                        only_stolen.discard(source)

    candidates -= only_stolen
    if not candidates:
        return

    candidates_by_attr = {}
    for candidate in candidates:
        candidates_by_attr.setdefault(candidate.attr, set()).add(candidate)

    result = run_analysis(
        blocks=ir.blocks,
        cfg=get_cfg(ir.blocks),
        gen_and_kill=BorrowGeneratorAttrsVisitor(self_reg, candidates, candidates_by_attr),
        initial=set(),
        kind=MUST_ANALYSIS,
        backward=False,
        universe=candidates,
    )
    for candidate in candidates:
        if all(candidate in result.before[position] for position in use_positions[candidate]):
            candidate.is_borrowed = True
