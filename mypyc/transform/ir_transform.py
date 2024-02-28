"""Helpers for implementing generic IR to IR transforms.

Subclass IRTransform and override any OpVisitor visit_* methods that perform
any IR changes. The default implementations implement an identity transform.
"""

from __future__ import annotations

from typing import Final

from mypyc.irbuild.ll_builder import LowLevelIRBuilder
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
    Extend,
    Float,
    FloatComparisonOp,
    FloatNeg,
    FloatOp,
    GetAttr,
    GetElementPtr,
    Goto,
    IncRef,
    DecRef,
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
    RaiseStandardError,
    RegisterOp,
    Return,
    SetAttr,
    SetMem,
    Truncate,
    TupleGet,
    TupleSet,
    Unborrow,
    Unbox,
    Unreachable,
    Value,
)



class IRTransform(OpVisitor[Value]):
    """Identity transform.

    Subclass and override to perform changes to IR.

    You can retain old BasicBlock and op references in ops. The transform
    will automatically patch these for you as needed.
    """

    def __init__(self, builder: LowLevelIRBuilder) -> None:
        self.builder = builder

    def transform_blocks(self,
                         blocks: list[BasicBlock]) -> None:
        op_map: dict[Value, Value] = {}
        block_map: dict[BasicBlock, BasicBlock] = {}
        for block in blocks:
            new_block = BasicBlock()
            new_block.error_handler = block.error_handler
            block_map[block] = new_block
            self.builder.activate_block(new_block)
            for op in block.ops:
                new_op = op.accept(self)
                if new_op is not op:
                    op_map[op] = new_op
        patcher = PatchVisitor(op_map, block_map)
        for block in self.builder.blocks:
            for op in block.ops:
                op.accept(patcher)
            if block.error_handler is not None:
                block.error_handler = block_map[block.error_handler]

    def add(self, op: Op) -> None:
        self.builder.add(op)

    def visit_goto(self, op: Goto) -> Value:
        return self.add(op)

    def visit_branch(self, op: Branch) -> Value:
        return self.add(op)

    def visit_return(self, op: Return) -> Value:
        return self.add(op)

    def visit_unreachable(self, op: Unreachable) -> Value:
        return self.add(op)

    def visit_assign(self, op: Assign) -> Value:
        return self.add(op)

    def visit_assign_multi(self, op: AssignMulti) -> Value:
        return self.add(op)

    def visit_load_error_value(self, op: LoadErrorValue) -> Value:
        return self.add(op)

    def visit_load_literal(self, op: LoadLiteral) -> Value:
        return self.add(op)

    def visit_get_attr(self, op: GetAttr) -> Value:
        return self.add(op)

    def visit_set_attr(self, op: SetAttr) -> Value:
        return self.add(op)

    def visit_load_static(self, op: LoadStatic) -> Value:
        return self.add(op)

    def visit_init_static(self, op: InitStatic) -> Value:
        return self.add(op)

    def visit_tuple_get(self, op: TupleGet) -> Value:
        return self.add(op)

    def visit_tuple_set(self, op: TupleSet) -> Value:
        return self.add(op)

    def visit_inc_ref(self, op: IncRef) -> Value:
        return self.add(op)

    def visit_dec_ref(self, op: DecRef) -> Value:
        return self.add(op)

    def visit_call(self, op: Call) -> Value:
        return self.add(op)

    def visit_method_call(self, op: MethodCall) -> Value:
        return self.add(op)

    def visit_cast(self, op: Cast) -> Value:
        return self.add(op)

    def visit_box(self, op: Box) -> Value:
        return self.add(op)

    def visit_unbox(self, op: Unbox) -> Value:
        return self.add(op)

    def visit_raise_standard_error(self, op: RaiseStandardError) -> Value:
        return self.add(op)

    def visit_call_c(self, op: CallC) -> Value:
        return self.add(op)

    def visit_truncate(self, op: Truncate) -> Value:
        return self.add(op)

    def visit_extend(self, op: Extend) -> Value:
        return self.add(op)

    def visit_load_global(self, op: LoadGlobal) -> Value:
        return self.add(op)

    def visit_int_op(self, op: IntOp) -> Value:
        return self.add(op)

    def visit_comparison_op(self, op: ComparisonOp) -> Value:
        return self.add(op)

    def visit_float_op(self, op: FloatOp) -> Value:
        return self.add(op)

    def visit_float_neg(self, op: FloatNeg) -> Value:
        return self.add(op)

    def visit_float_comparison_op(self, op: FloatComparisonOp) -> Value:
        return self.add(op)

    def visit_load_mem(self, op: LoadMem) -> Value:
        return self.add(op)

    def visit_set_mem(self, op: SetMem) -> Value:
        return self.add(op)

    def visit_get_element_ptr(self, op: GetElementPtr) -> Value:
        return self.add(op)

    def visit_load_address(self, op: LoadAddress) -> Value:
        return self.add(op)

    def visit_keep_alive(self, op: KeepAlive) -> Value:
        return self.add(op)

    def visit_unborrow(self, op: Unborrow) -> Value:
        return self.add(op)


class PatchVisitor(OpVisitor[None]):
    def __init__(self, ops: dict[Value, Value], blocks: dict[BasicBlock, BasicBlock]) -> None:
        self.ops: Final = ops
        self.blocks: Final = blocks

    def fix_op(self, op: Value) -> Value:
        return self.ops.get(op, op)

    def fix_block(self, block: BasicBlock) -> BasicBlock:
        return self.blocks.get(block, block)

    def visit_goto(self, op: Goto) -> None:
        op.label = self.fix_block(op.label)

    def visit_branch(self, op: Branch) -> None:
        op.value = self.fix_block(op.value)
        op.true = self.fix_block(op.true)
        op.false = self.fix_block(op.false)

    def visit_return(self, op: Return) -> None:
        op.value = self.fix_op(op.value)

    def visit_unreachable(self, op: Unreachable) -> None:
        pass

    def visit_assign(self, op: Assign) -> None:
        op.src = self.fix_op(op.src)

    def visit_assign_multi(self, op: AssignMulti) -> None:
        op.src = [self.fix_op(s) for s in self.fix_op(op.src)]

    def visit_load_error_value(self, op: LoadErrorValue) -> None:
        pass

    def visit_load_literal(self, op: LoadLiteral) -> None:
        pass

    def visit_get_attr(self, op: GetAttr) -> None:
        op.obj = self.fix_op(op.obj)

    def visit_set_attr(self, op: SetAttr) -> None:
        op.obj = self.fix_op(op.obj)
        op.src = self.fix_op(op.src)

    def visit_load_static(self, op: LoadStatic) -> None:
        pass

    def visit_init_static(self, op: InitStatic) -> None:
        op.value = self.fix_op(op.value)

    def visit_tuple_get(self, op: TupleGet) -> None:
        op.src = self.fix_op(op.src)

    def visit_tuple_set(self, op: TupleSet) -> None:
        op.items = [self.fix_op(item) for item in op.items]

    def visit_inc_ref(self, op: IncRef) -> None:
        op.src = self.fix_op(op.src)

    def visit_dec_ref(self, op: DecRef) -> None:
        op.src = self.fix_op(op.src)

    def visit_call(self, op: Call) -> None:
        op.args = [self.fix_op(arg) for arg in op.args]

    def visit_method_call(self, op: MethodCall) -> None:
        op.obj = self.fix_op(op.obj)
        op.args = [self.fix_op(arg) for arg in op.args]

    def visit_cast(self, op: Cast) -> None:
        op.src = self.fix_op(op.src)

    def visit_box(self, op: Box) -> None:
        op.src = self.fix_op(op.src)

    def visit_unbox(self, op: Unbox) -> None:
        op.src = self.fix_op(op.src)

    def visit_raise_standard_error(self, op: RaiseStandardError) -> None:
        if isinstance(op.value, Value):
            op.value = self.fix_op(op.value)

    def visit_call_c(self, op: CallC) -> None:
        op.args [self.fix_op(arg) for arg in op.args]

    def visit_truncate(self, op: Truncate) -> None:
        op.src = self.fix_op(op.src)

    def visit_extend(self, op: Extend) -> None:
        op.src = self.fix_op(op.src)

    def visit_load_global(self, op: LoadGlobal) -> None:
        pass

    def visit_int_op(self, op: IntOp) -> None:
        op.lhs = self.fix_op(op.lhs)
        op.rhs = self.fix_op(op.rhs)

    def visit_comparison_op(self, op: ComparisonOp) -> None:
        op.lhs = self.fix_op(op.lhs)
        op.rhs = self.fix_op(op.rhs)

    def visit_float_op(self, op: FloatOp) -> None:
        op.lhs = self.fix_op(op.lhs)
        op.rhs = self.fix_op(op.rhs)

    def visit_float_neg(self, op: FloatNeg) -> None:
        op.src = self.fix_op(op.src)

    def visit_float_comparison_op(self, op: FloatComparisonOp) -> None:
        op.lhs = self.fix_op(op.lhs)
        op.rhs = self.fix_op(op.rhs)

    def visit_load_mem(self, op: LoadMem) -> None:
        op.src = self.fix_op(op.src)

    def visit_set_mem(self, op: SetMem) -> None:
        op.dest = self.fix_op(op.dest)
        op.src = self.fix_op(op.src)

    def visit_get_element_ptr(self, op: GetElementPtr) -> None:
        op.src = self.fix_op(op.src)

    def visit_load_address(self, op: LoadAddress) -> None:
        if isinstance(op.src, LoadStatic):
            new = self.fix_op(op.src)
            assert isinstance(new, LoadStatic)
            op.src = new

    def visit_keep_alive(self, op: KeepAlive) -> None:
        op.src = [self.fix_op(s) for s in op.src]

    def visit_unborrow(self, op: Unborrow) -> None:
        op.src = self.fix_op(op.src)
