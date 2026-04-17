"""Fold ``char = Unbox(CPyStr_GetItem(s, i))`` into a direct int32 read.

Replaces the sequence "allocate 1-char PyObject -> unbox to char -> free
PyObject" (per iteration) with ``CPyStr_GetCharAt``, which reads the
codepoint directly as an int32. Error semantics are preserved: the helper
returns ``-113`` on out-of-range input, matching the int32 error sentinel.
"""

from __future__ import annotations

from mypyc.ir.deps import STR_EXTRA_OPS
from mypyc.ir.func_ir import FuncIR
from mypyc.ir.ops import Branch, CallC, DecRef, Goto, IncRef, Op, Unbox, Value
from mypyc.ir.rtypes import is_char_rprimitive
from mypyc.options import CompilerOptions

STR_INDEXERS = {
    "CPyStr_GetItem": "CPyStr_GetCharAt",
}


def do_char_str_index_fold(fn: FuncIR, options: CompilerOptions) -> None:
    # Collect char Unbox ops and a snapshot use-map (consumer ops per Value)
    # in a single pass. The map is read-only during candidate selection.
    uses: dict[Value, list[Op]] = {}
    unbox_targets: list[Unbox] = []
    for block in fn.blocks:
        for op in block.ops:
            if isinstance(op, Unbox) and is_char_rprimitive(op.type):
                unbox_targets.append(op)
            for src in op.sources():
                uses.setdefault(src, []).append(op)

    # Candidate: Unbox to char whose source is a str-indexing CallC, where
    # the CallC's other consumers are only IS_ERROR Branch / IncRef / DecRef.
    to_rewrite: list[tuple[CallC, Unbox]] = []
    call_c_results: set[Value] = set()
    for unbox in unbox_targets:
        src = unbox.src
        if not isinstance(src, CallC) or src.function_name not in STR_INDEXERS:
            continue
        compatible = True
        for consumer in uses.get(src, ()):
            if consumer is unbox:
                continue
            if isinstance(consumer, Branch) and consumer.op == Branch.IS_ERROR:
                continue
            if isinstance(consumer, (IncRef, DecRef)):
                continue
            compatible = False
            break
        if not compatible:
            continue
        to_rewrite.append((src, unbox))
        call_c_results.add(src)

    if not to_rewrite:
        return

    # Mutate each str-indexing CallC in place. Keeping the CallC identity
    # means existing IS_ERROR Branches keep pointing at it; the check
    # switches from NULL-PyObject* to -113-int32 automatically since mypyc
    # emits IS_ERROR based on the op's type.
    for call_c, unbox in to_rewrite:
        call_c.function_name = STR_INDEXERS[call_c.function_name]
        call_c.type = unbox.type
        deps = list(call_c.dependencies) if call_c.dependencies else []
        if STR_EXTRA_OPS not in deps:
            deps.append(STR_EXTRA_OPS)
            call_c.dependencies = deps

    # The Unbox's own IS_ERROR Branch is now redundant (CallC already
    # checks the sentinel). Replace with Goto to the success path.
    unboxes_to_remove = {unbox for _, unbox in to_rewrite}
    branches_to_drop: set[Op] = set()
    for unbox in unboxes_to_remove:
        for consumer in uses.get(unbox, ()):
            if isinstance(consumer, Branch) and consumer.op == Branch.IS_ERROR:
                branches_to_drop.add(consumer)

    # Redirect remaining references from each Unbox onto its CallC, drop
    # the Unbox ops, and drop IncRef/DecRef on the CallC (char is not
    # refcounted).
    unbox_to_callc = {unbox: call_c for call_c, unbox in to_rewrite}
    for block in fn.blocks:
        new_ops: list[Op] = []
        for op in block.ops:
            if op in unboxes_to_remove:
                continue
            if isinstance(op, (IncRef, DecRef)) and op.src in call_c_results:
                continue
            if op in branches_to_drop:
                assert isinstance(op, Branch)
                new_ops.append(Goto(op.false, op.line))
                continue
            srcs = op.sources()
            if any(isinstance(s, Unbox) and s in unbox_to_callc for s in srcs):
                op.set_sources(
                    [
                        unbox_to_callc[s] if isinstance(s, Unbox) and s in unbox_to_callc else s
                        for s in srcs
                    ]
                )
            new_ops.append(op)
        block.ops = new_ops
