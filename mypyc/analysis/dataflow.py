"""Data-flow analyses."""

from __future__ import annotations

from abc import abstractmethod
from collections.abc import Iterable, Iterator
from typing import Generic, TypeVar

from mypyc.ir.ops import (
    Assign,
    AssignMulti,
    BasicBlock,
    Box,
    Branch,
    Call,
    CallC,
    Cast,
    ComparisonOp,
    ControlOp,
    DecRef,
    Extend,
    Float,
    FloatComparisonOp,
    FloatNeg,
    FloatOp,
    GetAttr,
    GetElementPtr,
    Goto,
    IncRef,
    InitStatic,
    Integer,
    IntOp,
    KeepAlive,
    LoadAddress,
    LoadErrorValue,
    LoadGlobal,
    LoadLiteral,
    LoadMem,
    LoadStatic,
    MethodCall,
    Op,
    OpVisitor,
    PrimitiveOp,
    RaiseStandardError,
    RegisterOp,
    Return,
    SetAttr,
    SetElement,
    SetMem,
    Truncate,
    TupleGet,
    TupleSet,
    Unborrow,
    Unbox,
    Undef,
    Unreachable,
    Value,
)


class CFG:
    """Control-flow graph.

    Node 0 is always assumed to be the entry point. There must be a
    non-empty set of exits.
    """

    def __init__(
        self,
        succ: dict[BasicBlock, list[BasicBlock]],
        pred: dict[BasicBlock, list[BasicBlock]],
        exits: set[BasicBlock],
    ) -> None:
        assert exits
        self.succ = succ
        self.pred = pred
        self.exits = exits

    def __str__(self) -> str:
        exits = sorted(self.exits, key=lambda e: int(e.label))
        return f"exits: {exits}\nsucc: {self.succ}\npred: {self.pred}"


def get_cfg(blocks: list[BasicBlock], *, use_yields: bool = False) -> CFG:
    """Calculate basic block control-flow graph.

    If use_yields is set, then we treat returns inserted by yields as gotos
    instead of exits.
    """
    succ_map = {}
    pred_map: dict[BasicBlock, list[BasicBlock]] = {}
    exits = set()
    for block in blocks:
        assert not any(
            isinstance(op, ControlOp) for op in block.ops[:-1]
        ), "Control-flow ops must be at the end of blocks"

        if use_yields and isinstance(block.terminator, Return) and block.terminator.yield_target:
            succ = [block.terminator.yield_target]
        else:
            succ = list(block.terminator.targets())
        if not succ:
            exits.add(block)

        # Errors can occur anywhere inside a block, which means that
        # we can't assume that the entire block has executed before
        # jumping to the error handler. In our CFG construction, we
        # model this as saying that a block can jump to its error
        # handler or the error handlers of any of its normal
        # successors (to represent an error before that next block
        # completes). This works well for analyses like "must
        # defined", where it implies that registers assigned in a
        # block may be undefined in its error handler, but is in
        # general not a precise representation of reality; any
        # analyses that require more fidelity must wait until after
        # exception insertion.
        for error_point in [block] + succ:
            if error_point.error_handler:
                succ.append(error_point.error_handler)

        succ_map[block] = succ
        pred_map[block] = []
    for prev, nxt in succ_map.items():
        for label in nxt:
            pred_map[label].append(prev)
    return CFG(succ_map, pred_map, exits)


def get_real_target(label: BasicBlock) -> BasicBlock:
    if len(label.ops) == 1 and isinstance(label.ops[-1], Goto):
        label = label.ops[-1].label
    return label


def cleanup_cfg(blocks: list[BasicBlock]) -> None:
    """Cleanup the control flow graph.

    This eliminates obviously dead basic blocks and eliminates blocks that contain
    nothing but a single jump.

    There is a lot more that could be done.
    """
    changed = True
    while changed:
        # First collapse any jumps to basic block that only contain a goto
        for block in blocks:
            for i, tgt in enumerate(block.terminator.targets()):
                block.terminator.set_target(i, get_real_target(tgt))

        # Then delete any blocks that have no predecessors
        changed = False
        cfg = get_cfg(blocks)
        orig_blocks = blocks.copy()
        blocks.clear()
        for i, block in enumerate(orig_blocks):
            if i == 0 or cfg.pred[block]:
                blocks.append(block)
            else:
                changed = True


T = TypeVar("T")

AnalysisDict = dict[tuple[BasicBlock, int], set[T]]


class AnalysisResult(Generic[T]):
    def __init__(self, before: AnalysisDict[T], after: AnalysisDict[T]) -> None:
        self.before = before
        self.after = after

    def __str__(self) -> str:
        return f"before: {self.before}\nafter: {self.after}\n"


GenAndKill = tuple[set[T], set[T]]


class BaseAnalysisVisitor(OpVisitor[GenAndKill[T]]):
    def visit_goto(self, op: Goto) -> GenAndKill[T]:
        return set(), set()

    @abstractmethod
    def visit_register_op(self, op: RegisterOp) -> GenAndKill[T]:
        raise NotImplementedError

    @abstractmethod
    def visit_assign(self, op: Assign) -> GenAndKill[T]:
        raise NotImplementedError

    @abstractmethod
    def visit_assign_multi(self, op: AssignMulti) -> GenAndKill[T]:
        raise NotImplementedError

    @abstractmethod
    def visit_set_mem(self, op: SetMem) -> GenAndKill[T]:
        raise NotImplementedError

    def visit_call(self, op: Call) -> GenAndKill[T]:
        return self.visit_register_op(op)

    def visit_method_call(self, op: MethodCall) -> GenAndKill[T]:
        return self.visit_register_op(op)

    def visit_load_error_value(self, op: LoadErrorValue) -> GenAndKill[T]:
        return self.visit_register_op(op)

    def visit_load_literal(self, op: LoadLiteral) -> GenAndKill[T]:
        return self.visit_register_op(op)

    def visit_get_attr(self, op: GetAttr) -> GenAndKill[T]:
        return self.visit_register_op(op)

    def visit_set_attr(self, op: SetAttr) -> GenAndKill[T]:
        return self.visit_register_op(op)

    def visit_load_static(self, op: LoadStatic) -> GenAndKill[T]:
        return self.visit_register_op(op)

    def visit_init_static(self, op: InitStatic) -> GenAndKill[T]:
        return self.visit_register_op(op)

    def visit_tuple_get(self, op: TupleGet) -> GenAndKill[T]:
        return self.visit_register_op(op)

    def visit_tuple_set(self, op: TupleSet) -> GenAndKill[T]:
        return self.visit_register_op(op)

    def visit_box(self, op: Box) -> GenAndKill[T]:
        return self.visit_register_op(op)

    def visit_unbox(self, op: Unbox) -> GenAndKill[T]:
        return self.visit_register_op(op)

    def visit_cast(self, op: Cast) -> GenAndKill[T]:
        return self.visit_register_op(op)

    def visit_raise_standard_error(self, op: RaiseStandardError) -> GenAndKill[T]:
        return self.visit_register_op(op)

    def visit_call_c(self, op: CallC) -> GenAndKill[T]:
        return self.visit_register_op(op)

    def visit_primitive_op(self, op: PrimitiveOp) -> GenAndKill[T]:
        return self.visit_register_op(op)

    def visit_truncate(self, op: Truncate) -> GenAndKill[T]:
        return self.visit_register_op(op)

    def visit_extend(self, op: Extend) -> GenAndKill[T]:
        return self.visit_register_op(op)

    def visit_load_global(self, op: LoadGlobal) -> GenAndKill[T]:
        return self.visit_register_op(op)

    def visit_int_op(self, op: IntOp) -> GenAndKill[T]:
        return self.visit_register_op(op)

    def visit_float_op(self, op: FloatOp) -> GenAndKill[T]:
        return self.visit_register_op(op)

    def visit_float_neg(self, op: FloatNeg) -> GenAndKill[T]:
        return self.visit_register_op(op)

    def visit_comparison_op(self, op: ComparisonOp) -> GenAndKill[T]:
        return self.visit_register_op(op)

    def visit_float_comparison_op(self, op: FloatComparisonOp) -> GenAndKill[T]:
        return self.visit_register_op(op)

    def visit_load_mem(self, op: LoadMem) -> GenAndKill[T]:
        return self.visit_register_op(op)

    def visit_get_element_ptr(self, op: GetElementPtr) -> GenAndKill[T]:
        return self.visit_register_op(op)

    def visit_set_element(self, op: SetElement) -> GenAndKill[T]:
        return self.visit_register_op(op)

    def visit_load_address(self, op: LoadAddress) -> GenAndKill[T]:
        return self.visit_register_op(op)

    def visit_keep_alive(self, op: KeepAlive) -> GenAndKill[T]:
        return self.visit_register_op(op)

    def visit_unborrow(self, op: Unborrow) -> GenAndKill[T]:
        return self.visit_register_op(op)


class DefinedVisitor(BaseAnalysisVisitor[Value]):
    """Visitor for finding defined registers.

    Note that this only deals with registers and not temporaries, on
    the assumption that we never access temporaries when they might be
    undefined.

    If strict_errors is True, then we regard any use of LoadErrorValue
    as making a register undefined. Otherwise we only do if
    `undefines` is set on the error value.

    This lets us only consider the things we care about during
    uninitialized variable checking while capturing all possibly
    undefined things for refcounting.
    """

    def __init__(self, strict_errors: bool = False) -> None:
        self.strict_errors = strict_errors

    def visit_branch(self, op: Branch) -> GenAndKill[Value]:
        return set(), set()

    def visit_return(self, op: Return) -> GenAndKill[Value]:
        return set(), set()

    def visit_unreachable(self, op: Unreachable) -> GenAndKill[Value]:
        return set(), set()

    def visit_register_op(self, op: RegisterOp) -> GenAndKill[Value]:
        return set(), set()

    def visit_assign(self, op: Assign) -> GenAndKill[Value]:
        # Loading an error value may undefine the register.
        if isinstance(op.src, LoadErrorValue) and (op.src.undefines or self.strict_errors):
            return set(), {op.dest}
        else:
            return {op.dest}, set()

    def visit_assign_multi(self, op: AssignMulti) -> GenAndKill[Value]:
        # Array registers are special and we don't track the definedness of them.
        return set(), set()

    def visit_set_mem(self, op: SetMem) -> GenAndKill[Value]:
        return set(), set()


def analyze_maybe_defined_regs(
    blocks: list[BasicBlock], cfg: CFG, initial_defined: set[Value]
) -> AnalysisResult[Value]:
    """Calculate potentially defined registers at each CFG location.

    A register is defined if it has a value along some path from the initial location.
    """
    return run_analysis(
        blocks=blocks,
        cfg=cfg,
        gen_and_kill=DefinedVisitor(),
        initial=initial_defined,
        backward=False,
        kind=MAYBE_ANALYSIS,
    )


def analyze_must_defined_regs(
    blocks: list[BasicBlock],
    cfg: CFG,
    initial_defined: set[Value],
    regs: Iterable[Value],
    strict_errors: bool = False,
) -> AnalysisResult[Value]:
    """Calculate always defined registers at each CFG location.

    This analysis can work before exception insertion, since it is a
    sound assumption that registers defined in a block might not be
    initialized in its error handler.

    A register is defined if it has a value along all paths from the
    initial location.
    """
    return run_analysis(
        blocks=blocks,
        cfg=cfg,
        gen_and_kill=DefinedVisitor(strict_errors=strict_errors),
        initial=initial_defined,
        backward=False,
        kind=MUST_ANALYSIS,
        universe=set(regs),
    )


class BorrowedArgumentsVisitor(BaseAnalysisVisitor[Value]):
    def __init__(self, args: set[Value]) -> None:
        self.args = args

    def visit_branch(self, op: Branch) -> GenAndKill[Value]:
        return set(), set()

    def visit_return(self, op: Return) -> GenAndKill[Value]:
        return set(), set()

    def visit_unreachable(self, op: Unreachable) -> GenAndKill[Value]:
        return set(), set()

    def visit_register_op(self, op: RegisterOp) -> GenAndKill[Value]:
        return set(), set()

    def visit_assign(self, op: Assign) -> GenAndKill[Value]:
        if op.dest in self.args:
            return set(), {op.dest}
        return set(), set()

    def visit_assign_multi(self, op: AssignMulti) -> GenAndKill[Value]:
        return set(), set()

    def visit_set_mem(self, op: SetMem) -> GenAndKill[Value]:
        return set(), set()


def analyze_borrowed_arguments(
    blocks: list[BasicBlock], cfg: CFG, borrowed: set[Value]
) -> AnalysisResult[Value]:
    """Calculate arguments that can use references borrowed from the caller.

    When assigning to an argument, it no longer is borrowed.
    """
    return run_analysis(
        blocks=blocks,
        cfg=cfg,
        gen_and_kill=BorrowedArgumentsVisitor(borrowed),
        initial=borrowed,
        backward=False,
        kind=MUST_ANALYSIS,
        universe=borrowed,
    )


class UndefinedVisitor(BaseAnalysisVisitor[Value]):
    def visit_branch(self, op: Branch) -> GenAndKill[Value]:
        return set(), set()

    def visit_return(self, op: Return) -> GenAndKill[Value]:
        return set(), set()

    def visit_unreachable(self, op: Unreachable) -> GenAndKill[Value]:
        return set(), set()

    def visit_register_op(self, op: RegisterOp) -> GenAndKill[Value]:
        return set(), {op} if not op.is_void else set()

    def visit_assign(self, op: Assign) -> GenAndKill[Value]:
        return set(), {op.dest}

    def visit_assign_multi(self, op: AssignMulti) -> GenAndKill[Value]:
        return set(), {op.dest}

    def visit_set_mem(self, op: SetMem) -> GenAndKill[Value]:
        return set(), set()


def non_trivial_sources(op: Op) -> set[Value]:
    result = set()
    for source in op.sources():
        if not isinstance(source, (Integer, Float, Undef)):
            result.add(source)
    return result


class LivenessVisitor(BaseAnalysisVisitor[Value]):
    def visit_branch(self, op: Branch) -> GenAndKill[Value]:
        return non_trivial_sources(op), set()

    def visit_return(self, op: Return) -> GenAndKill[Value]:
        if not isinstance(op.value, (Integer, Float)):
            return {op.value}, set()
        else:
            return set(), set()

    def visit_unreachable(self, op: Unreachable) -> GenAndKill[Value]:
        return set(), set()

    def visit_register_op(self, op: RegisterOp) -> GenAndKill[Value]:
        gen = non_trivial_sources(op)
        if not op.is_void:
            return gen, {op}
        else:
            return gen, set()

    def visit_assign(self, op: Assign) -> GenAndKill[Value]:
        return non_trivial_sources(op), {op.dest}

    def visit_assign_multi(self, op: AssignMulti) -> GenAndKill[Value]:
        return non_trivial_sources(op), {op.dest}

    def visit_set_mem(self, op: SetMem) -> GenAndKill[Value]:
        return non_trivial_sources(op), set()

    def visit_inc_ref(self, op: IncRef) -> GenAndKill[Value]:
        return set(), set()

    def visit_dec_ref(self, op: DecRef) -> GenAndKill[Value]:
        return set(), set()


def analyze_live_regs(blocks: list[BasicBlock], cfg: CFG) -> AnalysisResult[Value]:
    """Calculate live registers at each CFG location.

    A register is live at a location if it can be read along some CFG path starting
    from the location.
    """
    return run_analysis(
        blocks=blocks,
        cfg=cfg,
        gen_and_kill=LivenessVisitor(),
        initial=set(),
        backward=True,
        kind=MAYBE_ANALYSIS,
    )


# Analysis kinds
MUST_ANALYSIS = 0
MAYBE_ANALYSIS = 1


def run_analysis(
    blocks: list[BasicBlock],
    cfg: CFG,
    gen_and_kill: OpVisitor[GenAndKill[T]],
    initial: set[T],
    kind: int,
    backward: bool,
    universe: set[T] | None = None,
) -> AnalysisResult[T]:
    """Run a general set-based data flow analysis.

    Args:
        blocks: All basic blocks
        cfg: Control-flow graph for the code
        gen_and_kill: Implementation of gen and kill functions for each op
        initial: Value of analysis for the entry points (for a forward analysis) or the
            exit points (for a backward analysis)
        kind: MUST_ANALYSIS or MAYBE_ANALYSIS
        backward: If False, the analysis is a forward analysis; it's backward otherwise
        universe: For a must analysis, the set of all possible values. This is the starting
            value for the work list algorithm, which will narrow this down until reaching a
            fixed point. For a maybe analysis the iteration always starts from an empty set
            and this argument is ignored.

    Return analysis results: (before, after)
    """
    block_gen = {}
    block_kill = {}

    # Calculate kill and gen sets for entire basic blocks.
    for block in blocks:
        gen: set[T] = set()
        kill: set[T] = set()
        ops = block.ops
        if backward:
            ops = list(reversed(ops))
        for op in ops:
            opgen, opkill = op.accept(gen_and_kill)
            gen = (gen - opkill) | opgen
            kill = (kill - opgen) | opkill
        block_gen[block] = gen
        block_kill[block] = kill

    # Set up initial state for worklist algorithm.
    worklist = list(blocks)
    if not backward:
        worklist.reverse()  # Reverse for a small performance improvement
    workset = set(worklist)
    before: dict[BasicBlock, set[T]] = {}
    after: dict[BasicBlock, set[T]] = {}
    for block in blocks:
        if kind == MAYBE_ANALYSIS:
            before[block] = set()
            after[block] = set()
        else:
            assert universe is not None, "Universe must be defined for a must analysis"
            before[block] = set(universe)
            after[block] = set(universe)

    if backward:
        pred_map = cfg.succ
        succ_map = cfg.pred
    else:
        pred_map = cfg.pred
        succ_map = cfg.succ

    # Run work list algorithm to generate in and out sets for each basic block.
    while worklist:
        label = worklist.pop()
        workset.remove(label)
        if pred_map[label]:
            new_before: set[T] | None = None
            for pred in pred_map[label]:
                if new_before is None:
                    new_before = set(after[pred])
                elif kind == MAYBE_ANALYSIS:
                    new_before |= after[pred]
                else:
                    new_before &= after[pred]
            assert new_before is not None
        else:
            new_before = set(initial)
        before[label] = new_before
        new_after = (new_before - block_kill[label]) | block_gen[label]
        if new_after != after[label]:
            for succ in succ_map[label]:
                if succ not in workset:
                    worklist.append(succ)
                    workset.add(succ)
        after[label] = new_after

    # Run algorithm for each basic block to generate opcode-level sets.
    op_before: dict[tuple[BasicBlock, int], set[T]] = {}
    op_after: dict[tuple[BasicBlock, int], set[T]] = {}
    for block in blocks:
        label = block
        cur = before[label]
        ops_enum: Iterator[tuple[int, Op]] = enumerate(block.ops)
        if backward:
            ops_enum = reversed(list(ops_enum))
        for idx, op in ops_enum:
            op_before[label, idx] = cur
            opgen, opkill = op.accept(gen_and_kill)
            cur = (cur - opkill) | opgen
            op_after[label, idx] = cur
    if backward:
        op_after, op_before = op_before, op_after

    return AnalysisResult(op_before, op_after)
