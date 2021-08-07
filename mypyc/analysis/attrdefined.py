"""Always defined attribute analysis.

An always defined attribute has some statements in __init__ that
always initialize the attribute when evaluated, and the attribute is
never read before initialization.

As soon as we encounter something that can execute arbitrary code, we
must stop inferring always defined attributes, since this code could
read the attribute values. We only allow a fairly restricted set of
operations.

We require that __del__ methods don't call gc.get_objects() and then
access partially initialized objects. Code like this could potentially
cause a segfault with a null pointer reference:

- enter __init__ of a native class C
- allocate an empty object (e.g. a list) in __init__
- cyclic garbage collector runs and calls __del__ that accesses the x
  attribute of C which has not been initialized -> segfault
- (if gc would not run) initialize the x attribute to a non-null value

This runs after actual IR building as a separate pass. Since we only
run this on __init__ methods, this analysis pass will be fairly quick.
"""

from typing import List, Set, Tuple

from mypyc.ir.ops import (
    Register, Assign, AssignMulti, SetMem, SetAttr, Branch, Return, Unreachable, GetAttr,
    RegisterOp, BasicBlock
)
from mypyc.ir.class_ir import ClassIR
from mypyc.analysis.dataflow import (
    BaseAnalysisVisitor, AnalysisResult, get_cfg, CFG, MAYBE_ANALYSIS, run_analysis
)
from mypyc.analysis.defined import analyze_arbitrary_execution

GenAndKill = Tuple[Set[str], Set[str]]


class AttributeMaybeDefinedVisitor(BaseAnalysisVisitor[str]):
    def __init__(self, self_reg: Register) -> None:
        self.self_reg = self_reg

    def visit_branch(self, op: Branch) -> Tuple[Set[str], Set[str]]:
        return set(), set()

    def visit_return(self, op: Return) -> Tuple[Set[str], Set[str]]:
        return set(), set()

    def visit_unreachable(self, op: Unreachable) -> Tuple[Set[str], Set[str]]:
        return set(), set()

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


def analyze_maybe_defined_attrs_in_init(blocks: List[BasicBlock],
                                        self_reg: Register,
                                        cfg: CFG) -> AnalysisResult[str]:
    return run_analysis(blocks=blocks,
                        cfg=cfg,
                        gen_and_kill=AttributeMaybeDefinedVisitor(self_reg),
                        initial=set(),
                        backward=False,
                        kind=MAYBE_ANALYSIS)


class AttributeMaybeUndefinedVisitor(BaseAnalysisVisitor[str]):
    def __init__(self, self_reg: Register) -> None:
        self.self_reg = self_reg

    def visit_branch(self, op: Branch) -> Tuple[Set[str], Set[str]]:
        return set(), set()

    def visit_return(self, op: Return) -> Tuple[Set[str], Set[str]]:
        return set(), set()

    def visit_unreachable(self, op: Unreachable) -> Tuple[Set[str], Set[str]]:
        return set(), set()

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


def analyze_maybe_undefined_attrs_in_init(blocks: List[BasicBlock],
                                          self_reg: Register,
                                          all_attrs: Set[str],
                                          cfg: CFG) -> AnalysisResult[str]:
    return run_analysis(blocks=blocks,
                        cfg=cfg,
                        gen_and_kill=AttributeMaybeUndefinedVisitor(self_reg),
                        initial=all_attrs,
                        backward=False,
                        kind=MAYBE_ANALYSIS)


def find_always_defined_attributes(blocks: List[BasicBlock],
                                   self_reg: Register,
                                   all_attrs: Set[str],
                                   maybe_defined: AnalysisResult[str],
                                   maybe_undefined: AnalysisResult[str],
                                   dirty: AnalysisResult[None]) -> Set[str]:
    attrs = all_attrs.copy()
    for block in blocks:
        for i, op in enumerate(block.ops):
            # If an attribute we read may be undefined, it isn't always defined.
            if isinstance(op, GetAttr) and op.obj is self_reg:
                if op.attr in maybe_undefined.before[block, i]:
                    attrs.discard(op.attr)
            # If a set attribute may be undefined or defined, don't consider it always defined.
            if isinstance(op, SetAttr) and op.obj is self_reg:
                attr = op.attr
                if (attr in maybe_undefined.before[block, i]
                        and attr in maybe_defined.before[block, i]):
                    attrs.discard(attr)
            if dirty.after[block, i]:
                if not dirty.before[block, i]:
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


def analyze_always_defined_attrs(class_irs: List[ClassIR]) -> None:
    for cl in class_irs:
        if (cl.is_trait
                or cl.inherits_python
                or cl.allow_interpreted_subclasses
                or cl.builtin_base is not None
                or cl.children is None
                or cl.children != []):
            # Give up
            continue
        m = cl.get_method('__init__')
        if m is None:
            continue
        self_reg = m.arg_regs[0]
        cfg = get_cfg(m.blocks)
        dirty = analyze_arbitrary_execution(m.blocks, self_reg, cfg)
        maybe_defined = analyze_maybe_defined_attrs_in_init(m.blocks, self_reg, cfg)
        all_attrs = set(cl.attributes)
        maybe_undefined = analyze_maybe_undefined_attrs_in_init(
            m.blocks, self_reg, all_attrs=all_attrs, cfg=cfg)

        always_defined = find_always_defined_attributes(
            m.blocks, self_reg, all_attrs, maybe_defined, maybe_undefined, dirty)

        cl._always_initialized_attrs = always_defined

        mark_attr_initialiation_ops(m.blocks, maybe_defined, dirty)
