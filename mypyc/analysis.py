"""Data-flow analyses."""

from abc import abstractmethod

from typing import Dict, Tuple, List, Set, TypeVar, Iterator, Generic

from mypyc.ops import (
    BasicBlock, OpVisitor, PrimitiveOp, Assign, LoadInt, RegisterOp, Goto,
    Branch, Return, Call, Environment, Box, Unbox, Cast, Op, Unreachable,
    TupleGet, GetAttr, SetAttr, PyCall, LoadStatic, PyGetAttr, Label, Register
)


class CFG:
    """Control-flow graph.

    Node 0 is always assumed to be the entry point. There must be a
    non-empty set of exits.
    """

    def __init__(self, succ: Dict[Label, List[Label]], pred: Dict[Label, List[Label]],
                 exits: Set[Label]) -> None:
        assert exits
        self.succ = succ
        self.pred = pred
        self.exits = exits


def get_cfg(blocks: List[BasicBlock]) -> CFG:
    """Calculate basic block control-flow graph.

    The result is a dictionary like this:

         basic block index -> (successors blocks, predecesssor blocks)
    """
    succ_map = {}
    pred_map = {}  # type: Dict[Label, List[Label]]
    exits = set()
    for block in blocks:
        label = block.label
        last = block.ops[-1]
        if isinstance(last, Branch):
            succ = [last.true, last.false]  # TODO: assume 1:1 correspondence between block index
                                            #       and label
        elif isinstance(last, Goto):
            succ = [last.label]
        else:
            succ = []
            exits.add(label)
        succ_map[label] = succ
        pred_map[label] = []
    for prev, nxt in succ_map.items():
        for label in nxt:
            pred_map[label].append(prev)
    return CFG(succ_map, pred_map, exits)


T = TypeVar('T')

AnalysisDict = Dict[Tuple[Label, int], Set[T]]

class AnalysisResult(Generic[T]):
    def __init__(self, before: AnalysisDict[T], after: AnalysisDict[T]) -> None:
        self.before = before
        self.after = after

GenAndKill = Tuple[Set[Register], Set[Register]]


class BaseAnalysisVisitor(OpVisitor[GenAndKill]):
    def visit_goto(self, op: Goto) -> GenAndKill:
        return set(), set()

    @abstractmethod
    def visit_register_op(self, op: RegisterOp) -> GenAndKill:
        raise NotImplementedError

    def visit_call(self, op: Call) -> GenAndKill:
        return self.visit_register_op(op)

    def visit_py_call(self, op: PyCall) -> GenAndKill:
        return self.visit_register_op(op)

    def visit_primitive_op(self, op: PrimitiveOp) -> GenAndKill:
        return self.visit_register_op(op)

    def visit_assign(self, op: Assign) -> GenAndKill:
        return self.visit_register_op(op)

    def visit_load_int(self, op: LoadInt) -> GenAndKill:
        return self.visit_register_op(op)

    def visit_get_attr(self, op: GetAttr) -> GenAndKill:
        return self.visit_register_op(op)

    def visit_set_attr(self, op: SetAttr) -> GenAndKill:
        return self.visit_register_op(op)

    def visit_load_static(self, op: LoadStatic) -> GenAndKill:
        return self.visit_register_op(op)

    def visit_py_get_attr(self, op: PyGetAttr) -> GenAndKill:
        return self.visit_register_op(op)

    def visit_tuple_get(self, op: TupleGet) -> GenAndKill:
        return self.visit_register_op(op)

    def visit_box(self, op: Box) -> GenAndKill:
        return self.visit_register_op(op)

    def visit_unbox(self, op: Unbox) -> GenAndKill:
        return self.visit_register_op(op)

    def visit_cast(self, op: Cast) -> GenAndKill:
        return self.visit_register_op(op)


class MaybeDefinedVisitor(BaseAnalysisVisitor):
    def visit_branch(self, op: Branch) -> GenAndKill:
        return set(), set()

    def visit_return(self, op: Return) -> GenAndKill:
        return set(), set()

    def visit_unreachable(self, op: Unreachable) -> GenAndKill:
        return set(), set()

    def visit_register_op(self, op: RegisterOp) -> GenAndKill:
        if op.dest is not None:
            return {op.dest}, set()
        else:
            return set(), set()


def analyze_maybe_defined_regs(blocks: List[BasicBlock],
                               cfg: CFG,
                               initial_defined: Set[Register]) -> AnalysisResult[Register]:
    """Calculate potentially defined registers at each CFG location.

    A register is defined if it has a value along some path from the initial location.
    """
    return run_analysis(blocks=blocks,
                        cfg=cfg,
                        gen_and_kill=MaybeDefinedVisitor(),
                        initial=initial_defined,
                        backward=False,
                        kind=MAYBE_ANALYSIS)


class MustDefinedVisitor(BaseAnalysisVisitor):
    # TODO: Merge with MaybeDefinedVisitor?

    def visit_branch(self, op: Branch) -> GenAndKill:
        return set(), set()

    def visit_return(self, op: Return) -> GenAndKill:
        return set(), set()

    def visit_unreachable(self, op: Unreachable) -> GenAndKill:
        return set(), set()

    def visit_register_op(self, op: RegisterOp) -> GenAndKill:
        if op.dest is not None:
            return {op.dest}, set()
        else:
            return set(), set()


def analyze_must_defined_regs(
        blocks: List[BasicBlock],
        cfg: CFG,
        initial_defined: Set[Register],
        num_regs: int) -> AnalysisResult[Register]:
    """Calculate always defined registers at each CFG location.

    A register is defined if it has a value along all paths from the initial location.
    """
    return run_analysis(blocks=blocks,
                        cfg=cfg,
                        gen_and_kill=MustDefinedVisitor(),
                        initial=initial_defined,
                        backward=False,
                        kind=MUST_ANALYSIS,
                        universe=set([Register(r) for r in range(num_regs)]))


class BorrowedArgumentsVisitor(BaseAnalysisVisitor):
    def __init__(self, args: Set[Register]) -> None:
        self.args = args

    def visit_branch(self, op: Branch) -> GenAndKill:
        return set(), set()

    def visit_return(self, op: Return) -> GenAndKill:
        return set(), set()

    def visit_unreachable(self, op: Unreachable) -> GenAndKill:
        return set(), set()

    def visit_register_op(self, op: RegisterOp) -> GenAndKill:
        if op.dest in self.args:
            return set(), {op.dest}
        return set(), set()


def analyze_borrowed_arguments(
        blocks: List[BasicBlock],
        cfg: CFG,
        args: Set[Register]) -> AnalysisResult[Register]:
    """Calculate arguments that can use references borrowed from the caller.

    When assigning to an argument, it no longer is borrowed.
    """
    return run_analysis(blocks=blocks,
                        cfg=cfg,
                        gen_and_kill=BorrowedArgumentsVisitor(args),
                        initial=args,
                        backward=False,
                        kind=MUST_ANALYSIS,
                        universe=args)


class UndefinedVisitor(BaseAnalysisVisitor):
    def visit_branch(self, op: Branch) -> GenAndKill:
        return set(), set()

    def visit_return(self, op: Return) -> GenAndKill:
        return set(), set()

    def visit_unreachable(self, op: Unreachable) -> GenAndKill:
        return set(), set()

    def visit_register_op(self, op: RegisterOp) -> GenAndKill:
        return set(), {op.dest}


def analyze_undefined_regs(blocks: List[BasicBlock],
                           cfg: CFG,
                           env: Environment,
                           initial_defined: Set[Register]) -> AnalysisResult[Register]:
    """Calculate potentially undefined registers at each CFG location.

    A register is undefined if there is some path from initial block
    where it has an undefined value.
    """
    initial_undefined = {Register(reg) for reg in range(len(env.names)) if Register(reg) not in initial_defined}
    return run_analysis(blocks=blocks,
                        cfg=cfg,
                        gen_and_kill=UndefinedVisitor(),
                        initial=initial_undefined,
                        backward=False,
                        kind=MAYBE_ANALYSIS)


class LivenessVisitor(BaseAnalysisVisitor):
    def visit_branch(self, op: Branch) -> GenAndKill:
        return set(op.sources()), set()

    def visit_return(self, op: Return) -> GenAndKill:
        return {op.reg}, set()

    def visit_unreachable(self, op: Unreachable) -> GenAndKill:
        return set(), set()

    def visit_register_op(self, op: RegisterOp) -> GenAndKill:
        gen = set(op.sources())
        if op.dest is not None:
            return gen, {op.dest}
        else:
            return gen, set()


def analyze_live_regs(blocks: List[BasicBlock],
                      cfg: CFG) -> AnalysisResult[Register]:
    """Calculate live registers at each CFG location.

    A register is live at a location if it can be read along some CFG path starting
    from the location.
    """
    return run_analysis(blocks=blocks,
                        cfg=cfg,
                        gen_and_kill=LivenessVisitor(),
                        initial=set(),
                        backward=True,
                        kind=MAYBE_ANALYSIS)


# Analysis kinds
MUST_ANALYSIS = 0
MAYBE_ANALYSIS = 1


# TODO the return type of this function is too complicated. Abtract it into its
# own class.

def run_analysis(blocks: List[BasicBlock],
                 cfg: CFG,
                 gen_and_kill: OpVisitor[Tuple[Set[T], Set[T]]],
                 initial: Set[T],
                 kind: int,
                 backward: bool,
                 universe: Set[T] = None) -> AnalysisResult[T]:
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
    if kind == MUST_ANALYSIS:
        assert universe is not None, "Universe must be defined for a must analysis"

    block_gen = {}
    block_kill = {}

    # Calculate kill and gen sets for entire basic blocks.
    for block in blocks:
        gen = set()  # type: Set[T]
        kill = set()  # type: Set[T]
        ops = block.ops
        if backward:
            ops = list(reversed(ops))
        for op in ops:
            opgen, opkill = op.accept(gen_and_kill)
            gen = ((gen - opkill) | opgen)
            kill = ((kill - opgen) | opkill)
        block_gen[block.label] =  gen
        block_kill[block.label] = kill

    # Set up initial state for worklist algorithm.
    worklist = [block.label for block in blocks]
    if not backward:
        worklist = worklist[::-1]  # Reverse for a small performance improvement
    workset = set(worklist)
    before = {}  # type: Dict[Label, Set[T]]
    after = {}  # type: Dict[Label, Set[T]]
    for block in blocks:
        if kind == MAYBE_ANALYSIS:
            before[block.label] = set()
            after[block.label] = set()
        else:
            before[block.label] = set(universe)
            after[block.label] = set(universe)

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
            new_before = None
            for pred in pred_map[label]:
                if new_before is None:
                    new_before = set(after[pred])
                elif kind == MAYBE_ANALYSIS:
                    new_before |= after[pred]
                else:
                    new_before &= after[pred]
        else:
            new_before = set(initial)
        before[label] = new_before
        new_after = (new_before | block_gen[label]) - block_kill[label]
        if new_after != after[label]:
            for succ in succ_map[label]:
                if succ not in workset:
                    worklist.append(succ)
                    workset.add(succ)
        after[label] = new_after

    # Run algorithm for each basic block to generate opcode-level sets.
    op_before = {} # type: Dict[Tuple[Label, int], Set[T]]
    op_after = {} # type: Dict[Tuple[Label, int], Set[T]]
    for block in blocks:
        label = block.label
        cur = before[label]
        ops_enum = enumerate(block.ops)  # type: Iterator[Tuple[int, Op]]
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
