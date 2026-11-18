"""Data-flow analyses."""

from __future__ import annotations

from abc import abstractmethod
from collections.abc import Collection, Iterable, Iterator, Set as AbstractSet
from typing import Any, Generic, TypeVar

from mypyc.ir.ops import (
    ERR_NEVER,
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
    GetElement,
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
    Register,
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
S = TypeVar("S")


class BitIndex(Generic[T]):
    """Assign bit positions to values, for use with BitSet."""

    def __init__(self) -> None:
        self.positions: dict[T, int] = {}
        self.values: list[T] = []

    def mask(self, values: Collection[T]) -> int:
        """Return a bit mask for values, assigning positions to new values."""
        positions = self.positions
        if len(values) > 8:
            for value in values:
                if value not in positions:
                    positions[value] = len(self.values)
                    self.values.append(value)
            return self.known_mask(values)
        # Gen and kill sets usually have only one or two items.
        result = 0
        for value in values:
            pos = positions.get(value)
            if pos is None:
                pos = len(self.values)
                positions[value] = pos
                self.values.append(value)
            result |= 1 << pos
        return result

    def known_mask(self, values: Iterable[object]) -> int:
        """Return a bit mask for those values that have a position (others are ignored)."""
        positions: dict[Any, int] = self.positions
        found = [pos for pos in map(positions.get, values) if pos is not None]
        if len(found) <= 8:
            result = 0
            for pos in found:
                result |= 1 << pos
            return result
        buf = bytearray((len(self.values) + 7) // 8)
        for pos in found:
            buf[pos >> 3] |= 1 << (pos & 7)
        return int.from_bytes(buf, "little")


class BitSet(AbstractSet[T]):
    """Immutable set of values represented as a bit mask.

    Bit i is set if index.values[i] is in the set. All the sets produced by a
    single analysis share the same index, so set operations between them are
    cheap integer operations. This uses much less memory than a set object:
    one bit per value that the analysis knows about instead of a hash table
    entry per element.
    """

    def __init__(self, bits: int, index: BitIndex[T]) -> None:
        self.bits = bits
        self.index = index

    def __contains__(self, value: object) -> bool:
        positions: dict[Any, int] = self.index.positions
        pos = positions.get(value)
        return pos is not None and (self.bits >> pos) & 1 == 1

    def positions(self) -> list[int]:
        """Return the positions of the set bits (in increasing order)."""
        # Least significant bit first, so that index i is position i.
        digits = bin(self.bits)[:1:-1]
        result = []
        pos = digits.find("1")
        while pos >= 0:
            result.append(pos)
            pos = digits.find("1", pos + 1)
        return result

    def __iter__(self) -> Iterator[T]:
        values = self.index.values
        return iter([values[pos] for pos in self.positions()])

    def __len__(self) -> int:
        return self.bits.bit_count()

    def __bool__(self) -> bool:
        return self.bits != 0

    def _mask_of(self, other: AbstractSet[Any]) -> int:
        """Return a mask of the values in both self and other."""
        if isinstance(other, BitSet) and other.index is self.index:
            return self.bits & other.bits
        if len(self) <= len(other):
            # Like set operations, iterate over the smaller operand.
            values = self.index.values
            return self.index.known_mask(
                [values[pos] for pos in self.positions() if values[pos] in other]
            )
        return self.bits & self.index.known_mask(other)

    def __sub__(self, other: AbstractSet[Any]) -> AbstractSet[T]:
        return BitSet(self.bits & ~self._mask_of(other), self.index)

    def __and__(self, other: AbstractSet[Any]) -> AbstractSet[T]:
        return BitSet(self._mask_of(other), self.index)

    def __or__(self, other: AbstractSet[S]) -> AbstractSet[T | S]:
        if isinstance(other, BitSet) and other.index is self.index:
            return BitSet(self.bits | other.bits, self.index)
        result: set[T | S] = set(self)
        result.update(other)
        return result

    # The reflected operations are used when the left operand is a set. They must
    # return a set, since that's the type that the operation has with a set on the
    # left according to typeshed, and compiled code checks this.

    def __rand__(self, other: AbstractSet[S]) -> AbstractSet[S]:
        return {value for value in other if value in self}

    def __ror__(self, other: AbstractSet[S]) -> AbstractSet[T | S]:
        result: set[T | S] = set(other)
        result.update(self)
        return result

    def __rsub__(self, other: AbstractSet[S]) -> AbstractSet[S]:
        return {value for value in other if value not in self}

    def __repr__(self) -> str:
        return repr(set(self))


AnalysisDict = dict[tuple[BasicBlock, int], AbstractSet[T]]


class AnalysisResult(Generic[T]):
    def __init__(self, before: AnalysisDict[T], after: AnalysisDict[T]) -> None:
        self.before = before
        self.after = after

    def __str__(self) -> str:
        return f"before: {self.before}\nafter: {self.after}\n"


GenAndKill = tuple[AbstractSet[T], AbstractSet[T]]

_EMPTY: tuple[frozenset[Any], frozenset[Any]] = (frozenset(), frozenset())


class BaseAnalysisVisitor(OpVisitor[GenAndKill[T]]):
    def visit_goto(self, op: Goto) -> GenAndKill[T]:
        return _EMPTY

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

    def visit_inc_ref(self, op: IncRef) -> GenAndKill[T]:
        return self.visit_register_op(op)

    def visit_dec_ref(self, op: DecRef) -> GenAndKill[T]:
        return self.visit_register_op(op)

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

    def visit_get_element(self, op: GetElement) -> GenAndKill[T]:
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
        return _EMPTY

    def visit_return(self, op: Return) -> GenAndKill[Value]:
        return _EMPTY

    def visit_unreachable(self, op: Unreachable) -> GenAndKill[Value]:
        return _EMPTY

    def visit_register_op(self, op: RegisterOp) -> GenAndKill[Value]:
        return _EMPTY

    def visit_assign(self, op: Assign) -> GenAndKill[Value]:
        # Loading an error value may undefine the register.
        if isinstance(op.src, LoadErrorValue) and (op.src.undefines or self.strict_errors):
            return set(), {op.dest}
        else:
            return {op.dest}, set()

    def visit_assign_multi(self, op: AssignMulti) -> GenAndKill[Value]:
        # Array registers are special and we don't track the definedness of them.
        return _EMPTY

    def visit_set_mem(self, op: SetMem) -> GenAndKill[Value]:
        return _EMPTY


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
    index: BitIndex[Value] | None = None,
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
        index=index,
        gen_and_kill=DefinedVisitor(strict_errors=strict_errors),
        initial=initial_defined,
        backward=False,
        kind=MUST_ANALYSIS,
        # Only registers can be undefined (temporaries are always defined before use),
        # so leave everything else out of the universe to keep the sets small.
        universe={r for r in regs if isinstance(r, Register)},
    )


class BorrowedArgumentsVisitor(BaseAnalysisVisitor[Value]):
    def __init__(self, args: set[Value]) -> None:
        self.args = args

    def visit_branch(self, op: Branch) -> GenAndKill[Value]:
        return _EMPTY

    def visit_return(self, op: Return) -> GenAndKill[Value]:
        return _EMPTY

    def visit_unreachable(self, op: Unreachable) -> GenAndKill[Value]:
        return _EMPTY

    def visit_register_op(self, op: RegisterOp) -> GenAndKill[Value]:
        return _EMPTY

    def visit_assign(self, op: Assign) -> GenAndKill[Value]:
        if op.dest in self.args:
            return set(), {op.dest}
        return _EMPTY

    def visit_assign_multi(self, op: AssignMulti) -> GenAndKill[Value]:
        return _EMPTY

    def visit_set_mem(self, op: SetMem) -> GenAndKill[Value]:
        return _EMPTY


def analyze_borrowed_arguments(
    blocks: list[BasicBlock], cfg: CFG, borrowed: set[Value], index: BitIndex[Value] | None = None
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
        index=index,
    )


class UndefinedVisitor(BaseAnalysisVisitor[Value]):
    def visit_branch(self, op: Branch) -> GenAndKill[Value]:
        return _EMPTY

    def visit_return(self, op: Return) -> GenAndKill[Value]:
        return _EMPTY

    def visit_unreachable(self, op: Unreachable) -> GenAndKill[Value]:
        return _EMPTY

    def visit_register_op(self, op: RegisterOp) -> GenAndKill[Value]:
        return set(), {op} if not op.is_void else set()

    def visit_assign(self, op: Assign) -> GenAndKill[Value]:
        return set(), {op.dest}

    def visit_assign_multi(self, op: AssignMulti) -> GenAndKill[Value]:
        return set(), {op.dest}

    def visit_set_mem(self, op: SetMem) -> GenAndKill[Value]:
        return _EMPTY


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
            return _EMPTY

    def visit_unreachable(self, op: Unreachable) -> GenAndKill[Value]:
        return _EMPTY

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
        return _EMPTY

    def visit_dec_ref(self, op: DecRef) -> GenAndKill[Value]:
        return _EMPTY


def analyze_live_regs(
    blocks: list[BasicBlock], cfg: CFG, index: BitIndex[Value] | None = None
) -> AnalysisResult[Value]:
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
        index=index,
    )


def analyze_live_regs_with_exception_edges(
    blocks: list[BasicBlock],
) -> dict[BasicBlock, set[Value]]:
    """Calculate block-entry liveness before exception handling is inserted.

    Unlike get_cfg(), this models an error edge at each operation that can
    raise. This matters when an assignment later in the same block overwrites a
    value that the error handler can still read. Returns inserted for a yield
    are treated as edges to their continuation blocks.

    TODO: Unlike run_analysis(), this supports edges from the middle of basic
          blocks, so we reimplement data flow analysis here. Figure out a way
          to unify this with run_analysis().
    """
    visitor = LivenessVisitor()
    live_in: dict[BasicBlock, set[Value]] = {block: set() for block in blocks}

    while True:
        changed = False
        for block in reversed(blocks):
            terminator = block.terminator
            if isinstance(terminator, Return) and terminator.yield_target is not None:
                successors = (terminator.yield_target,)
            else:
                successors = terminator.targets()

            live: set[Value] = set()
            for successor in successors:
                live.update(live_in[successor])

            for op in reversed(block.ops):
                if (
                    block.error_handler is not None
                    and isinstance(op, RegisterOp)
                    and op.error_kind != ERR_NEVER
                ):
                    live.update(live_in[block.error_handler])
                gen, kill = op.accept(visitor)
                live.difference_update(kill)
                live.update(gen)

            if live != live_in[block]:
                live_in[block] = live
                changed = True

        if not changed:
            return live_in


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
    index: BitIndex[T] | None = None,
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
        index: Bit positions to use for the result sets (see BitSet). Set operations
            between results of analyses that share an index are fast.

    Return analysis results: (before, after)
    """
    # Sets are represented as bit masks (see BitSet), since a large function can
    # have thousands of values and blocks, and we need a set for each of them.
    if index is None:
        index = BitIndex()
    initial_bits = index.mask(initial)
    universe_bits = index.mask(universe) if universe is not None else 0

    # Calculate gen and kill masks for each op, and for entire basic blocks.
    op_gen_and_kill: dict[BasicBlock, list[tuple[int, int]]] = {}
    block_gen = {}
    block_kill = {}
    for block in blocks:
        op_masks = []
        gen = 0
        kill = 0
        ops = block.ops
        if backward:
            ops = list(reversed(ops))
        for op in ops:
            opgen_set, opkill_set = op.accept(gen_and_kill)
            opgen = index.mask(opgen_set) if opgen_set else 0
            opkill = index.mask(opkill_set) if opkill_set else 0
            op_masks.append((opgen, opkill))
            if opkill:
                gen &= ~opkill

            if opgen:
                gen |= opgen
                kill &= ~opgen

            if opkill:
                kill |= opkill

        op_gen_and_kill[block] = op_masks
        block_gen[block] = gen
        block_kill[block] = kill

    # Set up initial state for worklist algorithm.
    worklist = list(blocks)
    if not backward:
        worklist.reverse()  # Reverse for a small performance improvement
    workset = set(worklist)
    before: dict[BasicBlock, int] = {}
    after: dict[BasicBlock, int] = {}
    if kind == MAYBE_ANALYSIS:
        start = 0
    else:
        assert universe is not None, "Universe must be defined for a must analysis"
        start = universe_bits
    for block in blocks:
        before[block] = start
        after[block] = start

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
        preds = pred_map[label]
        if preds:
            new_before = after[preds[0]]
            for pred in preds[1:]:
                if kind == MAYBE_ANALYSIS:
                    new_before |= after[pred]
                else:
                    new_before &= after[pred]
        else:
            new_before = initial_bits
        before[label] = new_before
        new_after = (new_before & ~block_kill[label]) | block_gen[label]
        if new_after != after[label]:
            for succ in succ_map[label]:
                if succ not in workset:
                    worklist.append(succ)
                    workset.add(succ)
        after[label] = new_after

    # Run algorithm for each basic block to generate opcode-level sets.
    op_before: dict[tuple[BasicBlock, int], AbstractSet[T]] = {}
    op_after: dict[tuple[BasicBlock, int], AbstractSet[T]] = {}
    for block in blocks:
        label = block
        cur = before[label]
        cur_set = BitSet(cur, index)
        n = len(block.ops)
        for i, (opgen, opkill) in enumerate(op_gen_and_kill[block]):
            # The masks are in reverse op order for a backward analysis.
            idx = n - 1 - i if backward else i
            op_before[label, idx] = cur_set
            if opkill or opgen:
                cur = (cur & ~opkill) | opgen
                cur_set = BitSet(cur, index)
            op_after[label, idx] = cur_set
    if backward:
        op_after, op_before = op_before, op_after

    return AnalysisResult(op_before, op_after)
