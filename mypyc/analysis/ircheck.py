from typing import List, Union
from mypyc.ir.ops import (
    OpVisitor, BasicBlock, Register, Op, ControlOp, Goto, Branch, Return, Unreachable,
    Assign, AssignMulti, LoadErrorValue, LoadLiteral, GetAttr, SetAttr, LoadStatic,
    InitStatic, TupleGet, TupleSet, IncRef, DecRef, Call, MethodCall, Cast,
    Box, Unbox, RaiseStandardError, CallC, Truncate, LoadGlobal, IntOp, ComparisonOp,
    LoadMem, SetMem, GetElementPtr, LoadAddress, KeepAlive
)
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


def check_funcdef(fn: FuncIR) -> List[FnError]:
    """Check a list of basic blocks (e.g. from a function definition) in surrounding
    context (e.g. args).
    """
    # deal with args later
    assert not fn.arg_regs

    errors = []

    for block in fn.blocks:
        if not block.terminated:
            errors.append(FnError(
                source=block.ops[-1] if block.ops else block,
                desc="Block not terminated",
            ))

    op_checker = OpChecker(fn)
    for block in fn.blocks:
        for op in block.ops:
            op.accept(op_checker)

    return errors + op_checker.errors


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

    def visit_goto(self, op: Goto) -> None:                            
        self.check_control_op_targets(op)
              
    def visit_branch(self, op: Branch) -> None:                    
        self.check_control_op_targets(op)
                                                                       
    def visit_return(self, op: Return) -> None:
        # TODO: check return
        pass
                                                                                 
    def visit_unreachable(self, op: Unreachable) -> None:
        raise NotImplementedError           
                                           
    def visit_assign(self, op: Assign) -> None:
        raise NotImplementedError
                                        
    def visit_assign_multi(self, op: AssignMulti) -> None:
        raise NotImplementedError   
                                                                      
    def visit_load_error_value(self, op: LoadErrorValue) -> None:        
        raise NotImplementedError

    def visit_load_literal(self, op: LoadLiteral) -> None:
        raise NotImplementedError

    def visit_get_attr(self, op: GetAttr) -> None:
        raise NotImplementedError

    def visit_set_attr(self, op: SetAttr) -> None:
        raise NotImplementedError

    def visit_load_static(self, op: LoadStatic) -> None:
        raise NotImplementedError

    def visit_init_static(self, op: InitStatic) -> None:
        raise NotImplementedError

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
        raise NotImplementedError

    def visit_call_c(self, op: CallC) -> None:
        raise NotImplementedError

    def visit_truncate(self, op: Truncate) -> None:
        raise NotImplementedError

    def visit_load_global(self, op: LoadGlobal) -> None:
        raise NotImplementedError

    def visit_int_op(self, op: IntOp) -> None:
        raise NotImplementedError

    def visit_comparison_op(self, op: ComparisonOp) -> None:
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
        raise NotImplementedError
