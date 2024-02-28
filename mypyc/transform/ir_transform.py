"""Generic IR to IR transform.

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
    PrimitiveOp,
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
                op_map[op] = new_op
        patcher = PatchVisitor(op_map, block_map)
        for block in self.builder.blocks:
            for op in block.ops:
                op.accept(patcher)
            if block.error_handler is not None:
                block.error_handler = block_map[block.error_handler]

    def visit_goto(self, op: Goto) -> Value:
        return Goto(op.label, op.line)

    def visit_branch(self, op: Branch) -> Value:
        new = Branch(op.value, op.true, op.false, op.op, op.line, rare=op.rare)
        new.negated = op.negated
        new.traceback_entry = op.traceback_entry
        return self.builder.add(new)

    def visit_return(self, op: Return) -> Value:
        return self.builder.add(Return(op.value, op.line))

    def visit_unreachable(self, op: Unreachable) -> Value:
        return self.builder.add(Unreachable(op.line))

    def visit_assign(self, op: Assign) -> Value:
        return self.builder.add(Assign(op.dest, op.src, op.line))

    def visit_assign_multi(self, op: AssignMulti) -> Value:
        return self.builder.add(AssignMulti(op.dest, op.src, op.line))

    def visit_load_error_value(self, op: LoadErrorValue) -> Value:
        assert False # TODO

    def visit_load_literal(self, op: LoadLiteral) -> Value:
        assert False # TODO

    def visit_get_attr(self, op: GetAttr) -> Value:
        assert False # TODO

    def visit_set_attr(self, op: SetAttr) -> Value:
        assert False # TODO

    def visit_load_static(self, op: LoadStatic) -> Value:
        assert False # TODO

    def visit_init_static(self, op: InitStatic) -> Value:
        assert False # TODO

    def visit_tuple_get(self, op: TupleGet) -> Value:
        assert False # TODO

    def visit_tuple_set(self, op: TupleSet) -> Value:
        assert False # TODO

    def visit_inc_ref(self, op: IncRef) -> Value:
        return self.builder.add(IncRef(op.src, op.line))

    def visit_dec_ref(self, op: DecRef) -> Value:
        return self.builder.add(DecRef(src=op.src, is_xdec=op.is_xdec, line=op.line))

    def visit_call(self, op: Call) -> Value:
        new = Call(op.fn, op.args, op.line)
        new.error_kind = op.error_kind
        new.type = op.type
        return self.builder.add(new)

    def visit_method_call(self, op: MethodCall) -> Value:
        new = MethodCall(op.obj, op.method, op.args, op.line)
        new.receiver_type = op.receiver_type
        new.type = op.type
        new.error_kind = op.error_kind
        return self.builder.add(new)

    def visit_cast(self, op: Cast) -> Value:
        return self.builder.add(Cast(op.src, op.type, op.line, borrow=op.is_borrowed))

    def visit_box(self, op: Box) -> Value:
        return self.builder.add(Box(op.src, op.line))

    def visit_unbox(self, op: Unbox) -> Value:
        return self.builder.add(Unbox(op.src, op.type, op.line))

    def visit_raise_standard_error(self, op: RaiseStandardError) -> Value:
        return self.builder.add(RaiseStandardError(op.class_name, op.value, op.line))

    def visit_call_c(self, op: CallC) -> Value:
        return self.builder.add(CallC(function_name=op.function_name,
                     args=op.args,
                     ret_type=op.type,
                     steals=op.steals,
                     is_borrowed=op.is_borrowed,
                     error_kind=op.error_kind,
                     line=op.line,
                     var_arg_idx=op.var_arg_idx))

    def visit_primitive_op(self, op: PrimitiveOp) -> Value:
        return self.builder.add(PrimitiveOp(op.args, op.desc, op.type_args, op.line))

    def visit_truncate(self, op: Truncate) -> Value:
        return self.builder.add(Truncate(op.src, op.type, op.line))

    def visit_extend(self, op: Extend) -> Value:
        return self.builder.add(Extend(op.src, op.type, signed=op.signed, line=op.line))

    def visit_load_global(self, op: LoadGlobal) -> Value:
        return self.builder.add(LoadGlobal(op.type, op.identifier, line=op.line, ann=op.ann))

    def visit_int_op(self, op: IntOp) -> Value:
        return self.builder.add(IntOp(type=op.type, lhs=op.lhs, rhs=op.rhs, op=op.op,
                                      line=op.line))

    def visit_comparison_op(self, op: ComparisonOp) -> Value:
        return self.builder.add(ComparisonOp(lhs=op.lhs, rhs=op.rhs, op=op.op, line=op.line))

    def visit_float_op(self, op: FloatOp) -> Value:
        return self.builder.add(FloatOp(lhs=op.lhs, rhs=op.rhs, op=op.op, line=op.line))

    def visit_float_neg(self, op: FloatNeg) -> Value:
        return self.builder.add(FloatNeg(op.src, op.line))

    def visit_float_comparison_op(self, op: FloatComparisonOp) -> Value:
        return self.builder.add(FloatComparisonOp(lhs=op.lhs, rhs=op.rhs, op=op.op, line=op.line))

    def visit_load_mem(self, op: LoadMem) -> Value:
        return self.builder.add(LoadMem(op.type, op.src, op.line))

    def visit_set_mem(self, op: SetMem) -> Value:
        return self.builder.add(SetMem(op.dest_type, op.dest, op.src, op.line))

    def visit_get_element_ptr(self, op: GetElementPtr) -> Value:
        return self.builder.add(GetElementPtr(op.src, op.src_type, op.field, op.line))

    def visit_load_address(self, op: LoadAddress) -> Value:
        return self.builder.add(LoadAddress(op.type, op.src, op.line))

    def visit_keep_alive(self, op: KeepAlive) -> Value:
        return self.builder.add(KeepAlive(op.src, steal=op.steal))

    def visit_unborrow(self, op: Unborrow) -> Value:
        return self.builder.add(Unborrow(op.src, op.line))


class PatchVisitor(OpVisitor[None]):
    def __init__(self, ops: dict[Value, Value], blocks: dict[BasicBlock, BasicBlock]) -> None:
        self.ops: Final = ops
        self.blocks: Final = blocks

    def visit_goto(self, op: Goto) -> None:
        op.label = self.blocks.get(op.label, op.label)

    def visit_branch(self, op: Branch) -> None:
        op.value = self.ops.get(op.value, op.value)
        op.true = self.blocks.get(op.true, op.true)
        op.false = self.blocks.get(op.false, op.false)

    def visit_return(self, op: Return) -> None:
        op.value = self.ops.get(op.value, op.value)

    def visit_unreachable(self, op: Unreachable) -> None:
        pass

    def visit_assign(self, op: Assign) -> None:
        # TODO
        raise NotImplementedError

    def visit_assign_multi(self, op: AssignMulti) -> None:
        raise NotImplementedError

    def visit_load_error_value(self, op: LoadErrorValue) -> None:
        pass

    def visit_load_literal(self, op: LoadLiteral) -> None:
        pass

    def visit_get_attr(self, op: GetAttr) -> None:
        op.obj = self.ops.get(op.obj, op.obj)

    def visit_set_attr(self, op: SetAttr) -> None:
        op.obj = self.ops.get(op.obj, op.obj)
        op.src = self.ops.get(op.src, op.src)

    def visit_load_static(self, op: LoadStatic) -> None:
        pass

    def visit_init_static(self, op: InitStatic) -> None:
        op.value = self.ops.get(op.value, op.value)

    def visit_tuple_get(self, op: TupleGet) -> None:
        raise NotImplementedError

    def visit_tuple_set(self, op: TupleSet) -> None:
        raise NotImplementedError

    def visit_inc_ref(self, op: IncRef) -> None:
        raise NotImplementedError

    def visit_dec_ref(self, op: DecRef) -> None:
        raise NotImplementedError

    def visit_call(self, op: Call) -> None:
        raise NotImplementedError

    def visit_method_call(self, op: MethodCall) -> None:
        raise NotImplementedError

    def visit_cast(self, op: Cast) -> None:
        raise NotImplementedError

    def visit_box(self, op: Box) -> None:
        raise NotImplementedError

    def visit_unbox(self, op: Unbox) -> None:
        raise NotImplementedError

    def visit_raise_standard_error(self, op: RaiseStandardError) -> None:
        if isinstance(op.value, Value):
            op.value = self.ops.get(op.value, op.value)

    def visit_call_c(self, op: CallC) -> None:
        raise NotImplementedError

    def visit_primitive_op(self, op: PrimitiveOp) -> None:
        raise NotImplementedError

    def visit_truncate(self, op: Truncate) -> None:
        raise NotImplementedError

    def visit_extend(self, op: Extend) -> None:
        raise NotImplementedError

    def visit_load_global(self, op: LoadGlobal) -> None:
        raise NotImplementedError

    def visit_int_op(self, op: IntOp) -> None:
        raise NotImplementedError

    def visit_comparison_op(self, op: ComparisonOp) -> None:
        raise NotImplementedError

    def visit_float_op(self, op: FloatOp) -> None:
        raise NotImplementedError

    def visit_float_neg(self, op: FloatNeg) -> None:
        raise NotImplementedError

    def visit_float_comparison_op(self, op: FloatComparisonOp) -> None:
        raise NotImplementedError

    def visit_load_mem(self, op: LoadMem) -> None:
        raise NotImplementedError

    def visit_set_mem(self, op: SetMem) -> None:
        raise NotImplementedError

    def visit_get_element_ptr(self, op: GetElementPtr) -> None:
        raise NotImplementedError

    def visit_load_address(self, op: LoadAddress) -> None:
        raise NotImplementedError

    def visit_keep_alive(self, op: KeepAlive) -> None:
        op.src = [self.ops.get(s, s) for s in op.src]

    def visit_unborrow(self, op: Unborrow) -> None:
        op.src = self.ops.get(op.src, op.src)
