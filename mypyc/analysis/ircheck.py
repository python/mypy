"""Utilities for checking that internal ir is valid and consistent."""
from typing import List, Union, Set
from mypyc.ir.pprint import format_func
from mypyc.ir.ops import (
    OpVisitor, BasicBlock, Op, ControlOp, Goto, Branch, Return, Unreachable,
    Assign, AssignMulti, LoadErrorValue, LoadLiteral, GetAttr, SetAttr, LoadStatic,
    InitStatic, TupleGet, TupleSet, IncRef, DecRef, Call, MethodCall, Cast,
    Box, Unbox, RaiseStandardError, CallC, Truncate, LoadGlobal, IntOp, ComparisonOp,
    LoadMem, SetMem, GetElementPtr, LoadAddress, KeepAlive, Register, Integer,
    BaseAssign
)
from mypyc.ir.rtypes import RType, RPrimitive, RUnion, is_object_rprimitive, RInstance, RArray, int_rprimitive, list_rprimitive, dict_rprimitive, set_rprimitive, range_rprimitive, str_rprimitive, bytes_rprimitive, tuple_rprimitive
from mypyc.ir.func_ir import FuncIR


class FnError(object):
    def __init__(self, source: Union[Op, BasicBlock], desc: str) -> None:
        self.source = source
        self.desc = desc

    def __eq__(self, other: object) -> bool:
        return isinstance(other, FnError) and self.source == other.source and \
            self.desc == other.desc

    def __repr__(self) -> str:
        return f"FnError(source={self.source}, desc={self.desc})"


def check_func_ir(fn: FuncIR) -> List[FnError]:
    """Applies validations to a given function ir and returns a list of errors found."""
    errors = []

    for block in fn.blocks:
        if not block.terminated:
            errors.append(FnError(
                source=block.ops[-1] if block.ops else block,
                desc="Block not terminated",
            ))

    errors.extend(check_op_sources_valid(fn))
    if errors:
        return errors

    op_checker = OpChecker(fn)
    for block in fn.blocks:
        for op in block.ops:
            op.accept(op_checker)

    return op_checker.errors


class IrCheckException(Exception):
    pass


def assert_func_ir_valid(fn: FuncIR) -> None:
    errors = check_func_ir(fn)
    if errors:
        raise IrCheckException("Internal error: Generated invalid IR: \n" + "\n".join(
            format_func(fn, [(e.source, e.desc) for e in errors])),
        )


def check_op_sources_valid(fn: FuncIR) -> List[FnError]:
    errors = []
    valid_ops: Set[Op] = set()
    valid_registers: Set[Register] = set()

    for block in fn.blocks:
        valid_ops.update(block.ops)

        valid_registers.update([
            op.dest for op in block.ops if isinstance(op, BaseAssign)
        ])

    valid_registers.update(fn.arg_regs)

    for block in fn.blocks:
        for op in block.ops:
            for source in op.sources():
                if isinstance(source, Integer):
                    pass
                elif isinstance(source, Op):
                    if source not in valid_ops:
                        errors.append(FnError(source=op, desc=f"Invalid op reference to op of type {type(source).__name__}"))
                elif isinstance(source, Register):
                    if source not in valid_registers:
                        errors.append(FnError(source=op, desc=f"Invalid op reference to register {source.name}"))

    return errors


disjoint_types = set([
    int_rprimitive.name,
    bytes_rprimitive.name,
    str_rprimitive.name,
    dict_rprimitive.name,
    list_rprimitive.name,
    set_rprimitive.name,
    tuple_rprimitive.name,
    range_rprimitive.name,
])


def can_coerce_to(src: RType, dest: RType) -> bool:
    """Check if src can be assigned to dest_rtype.
    
    Currently okay to have false positives.
    """
    if isinstance(dest, RUnion):
        return any(can_coerce_to(src, d) for d in dest.items)

    if isinstance(dest, RPrimitive):
        if isinstance(src, RPrimitive):
            # If either src or dest is a disjoint type, then they must both be.
            if src.name in disjoint_types and dest.name in disjoint_types:
                return src.name == dest.name
            return src.size == dest.size
        if isinstance(src, RInstance):
            return is_object_rprimitive(dest)
        if isinstance(src, RUnion):
            # IR doesn't have the ability to narrow unions based on
            # control flow, so cannot be a strict all() here.
            return any(can_coerce_to(s, dest) for s in src.items)
        return False

    return True


class OpChecker(OpVisitor[None]):
    def __init__(self, parent_fn: FuncIR) -> None:
        self.parent_fn = parent_fn
        self.errors: List[FnError] = []

    def fail(self, source: Op, desc: str) -> None:
        self.errors.append(FnError(source=source, desc=desc))

    def check_control_op_targets(self, op: ControlOp) -> None:
        for target in op.targets():
            if target not in self.parent_fn.blocks:
                self.fail(source=op, desc=f"Invalid control operation target: {target.label}")

    def check_type_coercion(self, op: Op, src: RType, dest: RType) -> None:
        if not can_coerce_to(src, dest):
            self.fail(source=op, desc=f"Cannot coerce source type {src.name} to dest type {dest.name}")

    def visit_goto(self, op: Goto) -> None:
        self.check_control_op_targets(op)

    def visit_branch(self, op: Branch) -> None:
        self.check_control_op_targets(op)

    def visit_return(self, op: Return) -> None:
        self.check_type_coercion(op, op.value.type, self.parent_fn.decl.sig.ret_type)

    def visit_unreachable(self, op: Unreachable) -> None:
        pass

    def visit_assign(self, op: Assign) -> None:
        self.check_type_coercion(op, op.src.type, op.dest.type)

    def visit_assign_multi(self, op: AssignMulti) -> None:
        for src in op.src:
            assert isinstance(op.dest.type, RArray)
            self.check_type_coercion(op, src.type, op.dest.type.item_type)

    def visit_load_error_value(self, op: LoadErrorValue) -> None:
        pass

    def visit_load_literal(self, op: LoadLiteral) -> None:
        pass

    def visit_get_attr(self, op: GetAttr) -> None:
        pass

    def visit_set_attr(self, op: SetAttr) -> None:
        pass

    def visit_load_static(self, op: LoadStatic) -> None:
        pass

    def visit_init_static(self, op: InitStatic) -> None:
        pass

    def visit_tuple_get(self, op: TupleGet) -> None:
        pass

    def visit_tuple_set(self, op: TupleSet) -> None:
        pass

    def visit_inc_ref(self, op: IncRef) -> None:
        pass

    def visit_dec_ref(self, op: DecRef) -> None:
        pass

    def visit_call(self, op: Call) -> None:
        pass

    def visit_method_call(self, op: MethodCall) -> None:
        pass

    def visit_cast(self, op: Cast) -> None:
        pass

    def visit_box(self, op: Box) -> None:
        pass

    def visit_unbox(self, op: Unbox) -> None:
        pass

    def visit_raise_standard_error(self, op: RaiseStandardError) -> None:
        pass

    def visit_call_c(self, op: CallC) -> None:
        pass

    def visit_truncate(self, op: Truncate) -> None:
        pass

    def visit_load_global(self, op: LoadGlobal) -> None:
        pass

    def visit_int_op(self, op: IntOp) -> None:
        pass

    def visit_comparison_op(self, op: ComparisonOp) -> None:
        pass

    def visit_load_mem(self, op: LoadMem) -> None:
        pass

    def visit_set_mem(self, op: SetMem) -> None:
        pass

    def visit_get_element_ptr(self, op: GetElementPtr) -> None:
        pass

    def visit_load_address(self, op: LoadAddress) -> None:
        pass

    def visit_keep_alive(self, op: KeepAlive) -> None:
        pass
