"""Transform a mypy AST to the IR form (Intermediate Representation).

For example, consider a function like this:

   def f(x: int) -> int:
       return x * 2 + 1

It would be translated to something that conceptually looks like this:

   r0 = 2
   r1 = 1
   r2 = x * i0 :: int
   r3 = r2 + r1 :: int
   return r3
"""

from typing import Dict, List, Tuple, Optional

from mypy.nodes import (
    Node, MypyFile, FuncDef, ReturnStmt, AssignmentStmt, OpExpr, IntExpr, NameExpr, LDEF, Var,
    IfStmt, Node, UnaryExpr, ComparisonExpr, WhileStmt, Argument, CallExpr, IndexExpr, Block,
    Expression, ListExpr, ExpressionStmt, MemberExpr, ForStmt, RefExpr, Lvalue, BreakStmt,
    ContinueStmt, ConditionalExpr, OperatorAssignmentStmt, ARG_POS
)
from mypy.types import Type, Instance, CallableType, NoneTyp
from mypy.visitor import NodeVisitor
from mypy.subtypes import is_named_instance

from mypyc.ops import (
    BasicBlock, Environment, Op, LoadInt, RTType, Register, Return, FuncIR, Assign,
    PrimitiveOp, Branch, Goto, RuntimeArg, Call, Box, Unbox, Cast
)


def build_ir(module: MypyFile, types: Dict[Expression, Type]) -> List[FuncIR]:
    builder = IRBuilder(types)
    module.accept(builder)
    return builder.generated


def type_to_rttype(typ: Type) -> RTType:
    if isinstance(typ, Instance):
        if typ.type.fullname() == 'builtins.int':
            return RTType('int')
        elif typ.type.fullname() == 'builtins.bool':
            return RTType('bool')
        elif typ.type.fullname() == 'builtins.list':
            return RTType('list')
    elif isinstance(typ, NoneTyp):
        return RTType('None')
    assert False, '%s unsupported' % type(typ)


class AssignmentTarget(object):
    pass


class AssignmentTargetRegister(AssignmentTarget):
    def __init__(self, register: Register) -> None:
        self.register = register


class AssignmentTargetIndex(AssignmentTarget):
    def __init__(self, base_reg: Register, index_reg: Register) -> None:
        self.base_reg = base_reg
        self.index_reg = index_reg


class IRBuilder(NodeVisitor[int]):
    def __init__(self, types: Dict[Expression, Type]) -> None:
        self.types = types
        self.environment = Environment()
        self.environments = [self.environment]
        self.blocks = []  # type: List[List[BasicBlock]]
        self.generated = []  # type: List[FuncIR]
        self.targets = []  # type: List[int]
        self.break_gotos = []  # type: List[List[Goto]]
        self.continue_gotos = []  # type: List[List[Goto]]

    def visit_mypy_file(self, mypyfile: MypyFile) -> int:
        if mypyfile.fullname() in ('typing', 'abc'):
            # These module are special; their contents are currently all
            # built-in primitives.
            return -1
        for node in mypyfile.defs:
            node.accept(self)
        return -1

    def visit_func_def(self, fdef: FuncDef) -> int:
        self.enter()

        for arg in fdef.arguments:
            self.environment.add_local(arg.variable, type_to_rttype(arg.variable.type))
        fdef.body.accept(self)
        self.add_implicit_return()

        blocks, env = self.leave()
        args = self.convert_args(fdef)
        ret_type = self.convert_return_type(fdef)
        func = FuncIR(fdef.name(), args, ret_type, blocks, env)
        self.generated.append(func)
        return -1

    def convert_args(self, fdef: FuncDef) -> List[RuntimeArg]:
        assert isinstance(fdef.type, CallableType)
        ann = fdef.type
        return [RuntimeArg(arg.variable.name(), type_to_rttype(ann.arg_types[i]))
                for i, arg in enumerate(fdef.arguments)]

    def convert_return_type(self, fdef: FuncDef) -> RTType:
        assert isinstance(fdef.type, CallableType)
        return type_to_rttype(fdef.type.ret_type)

    def add_implicit_return(self) -> None:
        block = self.blocks[-1][-1]
        if not block.ops or not isinstance(block.ops[-1], Return):
            retval = self.environment.add_temp(RTType('None'))
            self.add(PrimitiveOp(retval, PrimitiveOp.NONE))
            self.add(Return(retval))

    def visit_block(self, block: Block) -> int:
        for stmt in block.body:
            stmt.accept(self)
        return -1

    def visit_expression_stmt(self, stmt: ExpressionStmt) -> int:
        self.accept(stmt.expr)
        return -1

    def visit_return_stmt(self, stmt: ReturnStmt) -> int:
        if stmt.expr:
            retval = self.accept(stmt.expr)
        else:
            retval = self.environment.add_temp(RTType('None'))
            self.add(PrimitiveOp(retval, PrimitiveOp.NONE))
        self.add(Return(retval))
        return -1

    def visit_assignment_stmt(self, stmt: AssignmentStmt) -> int:
        assert len(stmt.lvalues) == 1
        lvalue = stmt.lvalues[0]
        return self.assign(lvalue, stmt.rvalue, declared_type=stmt.type)

    def visit_operator_assignment_stmt(self, stmt: OperatorAssignmentStmt) -> int:
        target = self.get_assignment_target(stmt.lvalue, None)

        if isinstance(target, AssignmentTargetRegister):
            ltype = self.environment.types[target.register]
            rtype = type_to_rttype(self.types[stmt.rvalue])
            rreg = self.accept(stmt.rvalue)
            return self.binary_op(ltype, target.register, rtype, rreg, stmt.op, target=target.register)

        # NOTE: List index not supported yet for compound assignments.
        assert False, 'Unsupported lvalue: %r'

    def get_assignment_target(self, lvalue: Lvalue, declared_type: Optional[Type] = None) -> AssignmentTarget:
        if isinstance(lvalue, NameExpr):
            # Assign to local variable.
            assert lvalue.kind == LDEF
            if lvalue.is_def or declared_type is not None:
                # Define a new variable.
                assert isinstance(lvalue.node, Var)  # TODO: Can this fail?
                lvalue_num = self.environment.add_local(lvalue.node, self.node_type(lvalue))
            else:
                # Assign to a previously defined variable.
                assert isinstance(lvalue.node, Var)  # TODO: Can this fail?
                lvalue_num = self.environment.lookup(lvalue.node)

            return AssignmentTargetRegister(lvalue_num)
        elif isinstance(lvalue, IndexExpr):
            # Indexed assignment x[y] = e
            base_type = self.node_type(lvalue.base)
            index_type = self.node_type(lvalue.index)
            if base_type.name == 'list' and index_type.name == 'int':
                # Indexed list set
                base_reg = self.accept(lvalue.base)
                index_reg = self.accept(lvalue.index)
                return AssignmentTargetIndex(base_reg, index_reg)

        assert False, 'Unsupported lvalue: %r' % lvalue

    def assign_to_target(self,
            target: AssignmentTarget,
            rvalue: Expression,
            rvalue_type: Optional[RTType] = None) -> int:
        rvalue_type = rvalue_type or self.node_type(rvalue)

        if isinstance(target, AssignmentTargetRegister):
            return self.accept(rvalue, target=target.register)
        elif isinstance(target, AssignmentTargetIndex):
            item_reg = self.accept(rvalue)
            boxed_item_reg = self.box(item_reg, rvalue_type)
            self.add(PrimitiveOp(None, PrimitiveOp.LIST_SET, target.base_reg, target.index_reg,
                                 boxed_item_reg))
            return -1

        assert False, 'Unsupported assignment target'

    def assign(self,
               lvalue: Lvalue,
               rvalue: Expression,
               rvalue_type: Optional[RTType] = None,
               declared_type: Optional[Type] = None) -> int:
        target = self.get_assignment_target(lvalue, declared_type)
        return self.assign_to_target(target, rvalue, rvalue_type)

    def visit_if_stmt(self, stmt: IfStmt) -> int:
        # If statements are normalized
        assert len(stmt.expr) == 1

        branches = self.process_conditional(stmt.expr[0])
        if_body = self.new_block()
        self.set_branches(branches, True, if_body)
        stmt.body[0].accept(self)
        if_leave = self.add_leave()
        if stmt.else_body:
            else_body = self.new_block()
            self.set_branches(branches, False, else_body)
            stmt.else_body.accept(self)
            else_leave = self.add_leave()
            next = self.new_block()
            if else_leave:
                else_leave.label = next.label
        else:
            # No else block.
            next = self.new_block()
            self.set_branches(branches, False, next)
        if if_leave:
            if_leave.label = next.label
        return -1

    def add_leave(self) -> Optional[Goto]:
        if not self.blocks[-1][-1].ops or not isinstance(self.blocks[-1][-1].ops[-1], Return):
            leave = Goto(-1)
            self.add(leave)
            return leave
        return None

    def push_loop_stack(self) -> None:
        self.break_gotos.append([])
        self.continue_gotos.append([])

    def pop_loop_stack(self, continue_block: BasicBlock, break_block: BasicBlock) -> None:
        for continue_goto in self.continue_gotos.pop():
            continue_goto.label = continue_block.label

        for break_goto in self.break_gotos.pop():
            break_goto.label = break_block.label
        
    def visit_while_stmt(self, s: WhileStmt) -> int:
        self.push_loop_stack()

        # Split block so that we get a handle to the top of the loop.
        goto = Goto(-1)
        self.add(goto)
        top = self.new_block()
        goto.label = top.label
        branches = self.process_conditional(s.expr)

        body = self.new_block()
        # Bind "true" branches to the body block.
        self.set_branches(branches, True, body)
        s.body.accept(self)
        # Add branch to the top at the end of the body.
        self.add(Goto(top.label))
        next = self.new_block()
        # Bind "false" branches to the new block.
        self.set_branches(branches, False, next)

        self.pop_loop_stack(top, next)
        return -1

    def visit_for_stmt(self, s: ForStmt) -> int:
        if (isinstance(s.expr, CallExpr)
                and isinstance(s.expr.callee, RefExpr)
                and s.expr.callee.fullname == 'builtins.range'):
            self.push_loop_stack()

            # Special case for x in range(...)
            # TODO: Check argument counts and kinds; check the lvalue
            end = s.expr.args[0]
            end_reg = self.accept(end)

            # Initialize loop index to 0.
            index_reg = self.assign(s.index, IntExpr(0), RTType('int'))
            goto = Goto(-1)
            self.add(goto)

            # Add loop condition check.
            top = self.new_block()
            goto.label = top.label
            branch = Branch(index_reg, end_reg, -1, -1, Branch.INT_LT)
            self.add(branch)
            branches = [branch]

            body = self.new_block()
            self.set_branches(branches, True, body)
            s.body.accept(self)
            
            end_goto = Goto(-1)
            self.add(end_goto)
            end_block = self.new_block()
            end_goto.label = end_block.label

            # Increment index register.
            one_reg = self.alloc_temp(RTType('int'))
            self.add(LoadInt(one_reg, 1))
            self.add(PrimitiveOp(index_reg, PrimitiveOp.INT_ADD, index_reg, one_reg))

            # Go back to loop condition check.
            self.add(Goto(top.label))
            next = self.new_block()
            self.set_branches(branches, False, next)

            self.pop_loop_stack(end_block, next)
            return -1

        if self.node_type(s.expr).name == 'list':
            self.push_loop_stack()

            expr_reg = self.accept(s.expr)

            index_reg = self.alloc_temp(RTType('int'))
            self.add(LoadInt(index_reg, 0))

            one_reg = self.alloc_temp(RTType('int'))
            self.add(LoadInt(one_reg, 1))
            
            assert isinstance(s.index, NameExpr)
            assert isinstance(s.index.node, Var)
            lvalue_reg = self.environment.add_local(s.index.node, self.node_type(s.index))


            condition_block = self.goto_new_block()

            # For compatibility with python semantics we recalculate the length
            # at every iteration.
            len_reg = self.alloc_temp(RTType('int'))
            self.add(PrimitiveOp(len_reg, PrimitiveOp.LIST_LEN, expr_reg))
            
            branch = Branch(index_reg, len_reg, -1, -1, Branch.INT_LT)
            self.add(branch)
            branches = [branch]
            
            body_block = self.new_block()
            self.set_branches(branches, True, body_block)

            target_list_type = self.types[s.expr]
            assert isinstance(target_list_type, Instance)
            target_type = type_to_rttype(target_list_type.args[0])
            value_box = self.alloc_temp(RTType('object'))
            self.add(PrimitiveOp(value_box, PrimitiveOp.LIST_GET, expr_reg, index_reg))

            self.unbox(value_box, target_type, target=lvalue_reg)

            s.body.accept(self)

            end_block = self.goto_new_block()
            self.add(PrimitiveOp(index_reg, PrimitiveOp.INT_ADD, index_reg, one_reg))
            self.add(Goto(condition_block.label))

            next_block = self.new_block()
            self.set_branches(branches, False, next_block)

            self.pop_loop_stack(end_block, next_block)

            return -1
            
        assert False, 'for not supported'

    def visit_break_stmt(self, node: BreakStmt) -> int:
        self.break_gotos[-1].append(Goto(-1))
        self.add(self.break_gotos[-1][-1])
        return -1

    def visit_continue_stmt(self, node: ContinueStmt) -> int:
        self.continue_gotos[-1].append(Goto(-1))
        self.add(self.continue_gotos[-1][-1])
        return -1

    def node_type(self, node: Expression) -> RTType:
        mypy_type = self.types[node]
        return type_to_rttype(mypy_type)

    int_binary_ops = {
        '+': PrimitiveOp.INT_ADD,
        '-': PrimitiveOp.INT_SUB,
        '*': PrimitiveOp.INT_MUL,
        '//': PrimitiveOp.INT_DIV,
        '%': PrimitiveOp.INT_MOD,
        '&': PrimitiveOp.INT_AND,
        '|': PrimitiveOp.INT_OR,
        '^': PrimitiveOp.INT_XOR,
        '<<': PrimitiveOp.INT_SHL,
        '>>': PrimitiveOp.INT_SHR,
        '>>': PrimitiveOp.INT_SHR,
    }

    def visit_unary_expr(self, expr: UnaryExpr) -> int:
        if expr.op != '-':
            assert False, 'Unsupported unary operation'

        etype = type_to_rttype(self.types[expr.expr])
        reg = self.accept(expr.expr)
        if etype.name != 'int':
            assert False, 'Unsupported unary operation'
        
        target = self.alloc_target(RTType('int'))
        zero = self.accept(IntExpr(0))
        self.add(PrimitiveOp(target, PrimitiveOp.INT_SUB, zero, reg))

        return target

    def visit_op_expr(self, expr: OpExpr) -> int:
        ltype = type_to_rttype(self.types[expr.left])
        rtype = type_to_rttype(self.types[expr.right])
        lreg = self.accept(expr.left)
        rreg = self.accept(expr.right)
        return self.binary_op(ltype, lreg, rtype, rreg, expr.op)

    def binary_op(self, ltype: RTType, lreg: Register, rtype: RTType, rreg: Register, expr_op: str, target: Optional[Register] = None) -> Register:
        if ltype.name == 'int' and rtype.name == 'int':
            # Primitive int operation
            if target is None:
                target = self.alloc_target(RTType('int'))
            op = self.int_binary_ops[expr_op]
        elif ltype.name == 'list' or rtype.name == 'list':
            if rtype.name == 'list':
                ltype, rtype = rtype, ltype
                lreg, rreg = rreg, lreg
            if rtype.name != 'int':
                assert False, 'Unsupported binary operation'  # TODO: Operator overloading
            if target is None:
                target = self.alloc_target(RTType('list'))
            op = PrimitiveOp.LIST_REPEAT
        else:
            assert False, 'Unsupported binary operation'
        self.add(PrimitiveOp(target, op, lreg, rreg))
        return target

    def visit_index_expr(self, expr: IndexExpr) -> int:
        base_type = self.types[expr.base]
        index_type = self.types[expr.index]
        result_type = self.types[expr]
        if (is_named_instance(base_type, 'builtins.list') and
                is_named_instance(index_type, 'builtins.int')):
            # List indexing
            base_reg = self.accept(expr.base)
            index_reg = self.accept(expr.index)
            target_type = self.node_type(expr)
            tmp = self.alloc_temp(RTType('object'))
            self.add(PrimitiveOp(tmp, PrimitiveOp.LIST_GET, base_reg, index_reg))
            return self.unbox(tmp, target_type)
        assert False, 'Unsupported indexing operation'

    def visit_int_expr(self, expr: IntExpr) -> int:
        reg = self.alloc_target(RTType('int'))
        self.add(LoadInt(reg, expr.value))
        return reg

    def visit_name_expr(self, expr: NameExpr) -> int:
        # TODO: We assume that this is a Var node, which is very limited
        assert isinstance(expr.node, Var)
        if expr.node.fullname() == 'builtins.None':
            target = self.alloc_target(RTType('None'))
            self.add(PrimitiveOp(target, PrimitiveOp.NONE))
            return target
        elif expr.node.fullname() == 'builtins.True':
            target = self.alloc_target(RTType('bool'))
            self.add(PrimitiveOp(target, PrimitiveOp.TRUE))
            return target
        elif expr.node.fullname() == 'builtins.False':
            target = self.alloc_target(RTType('bool'))
            self.add(PrimitiveOp(target, PrimitiveOp.FALSE))
            return target

        reg = self.environment.lookup(expr.node)
        if self.targets[-1] < 0:
            return reg
        else:
            target = self.targets[-1]
            self.add(Assign(target, reg))
            return target

    def visit_call_expr(self, expr: CallExpr) -> int:
        if isinstance(expr.callee, MemberExpr):
            return self.translate_special_method_call(expr.callee, expr)
        assert isinstance(expr.callee, NameExpr)
        fn = expr.callee.name  # TODO: fullname
        if fn == 'len' and len(expr.args) == 1 and expr.arg_kinds == [ARG_POS]:
            target = self.alloc_target(RTType('int'))
            arg = self.accept(expr.args[0])
            self.add(PrimitiveOp(target, PrimitiveOp.LIST_LEN, arg))
        else:
            target = self.alloc_target(RTType('int'))
            args = [self.accept(arg) for arg in expr.args]
            self.add(Call(target, fn, args))
        return target

    def visit_conditional_expr(self, expr: ConditionalExpr) -> int:
        branches = self.process_conditional(expr.cond)
        target = self.alloc_target(type_to_rttype(self.types[expr]))

        if_body = self.new_block()
        self.set_branches(branches, True, if_body)
        self.accept(expr.if_expr, target=target)
        if_goto_next = Goto(-1)
        self.add(if_goto_next)

        else_body = self.new_block()
        self.set_branches(branches, False, else_body)
        self.accept(expr.else_expr, target=target)
        else_goto_next = Goto(-1)
        self.add(else_goto_next)

        next = self.new_block()
        if_goto_next.label = next.label
        else_goto_next.label = next.label

        return target

    def translate_special_method_call(self, callee: MemberExpr, expr: CallExpr) -> int:
        base_type = self.node_type(callee.expr)
        result_type = self.node_type(expr)
        base = self.accept(callee.expr)
        if callee.name == 'append' and base_type.name == 'list':
            target = -1  # TODO: Do we sometimes need to allocate a register?
            arg = self.box_expr(expr.args[0])
            self.add(PrimitiveOp(target, PrimitiveOp.LIST_APPEND, base, arg))
        else:
            assert False, 'Unsupported method call: %s.%s' % (base_type.name, callee.name)
        return target

    def visit_list_expr(self, expr: ListExpr) -> int:
        list_type = self.types[expr]
        assert isinstance(list_type, Instance)
        item_type = type_to_rttype(list_type.args[0])
        target = self.alloc_target(RTType('list'))
        items = []
        for item in expr.items:
            item_reg = self.accept(item)
            boxed = self.box(item_reg, item_type)
            items.append(boxed)
        self.add(PrimitiveOp(target, PrimitiveOp.NEW_LIST, *items))
        return target

    # Conditional expressions

    int_relative_ops = {
        '==': Branch.INT_EQ,
        '!=': Branch.INT_NE,
        '<': Branch.INT_LT,
        '<=': Branch.INT_LE,
        '>': Branch.INT_GT,
        '>=': Branch.INT_GE,
    }

    def process_conditional(self, e: Node) -> List[Branch]:
        if isinstance(e, ComparisonExpr):
            # TODO: Verify operand types.
            assert len(e.operators) == 1, 'more than 1 operator not supported'
            op = e.operators[0]
            if op in ['==', '!=', '<', '<=', '>', '>=']:
                # TODO: check operand types
                left = self.accept(e.operands[0])
                right = self.accept(e.operands[1])
                opcode = self.int_relative_ops[op]
                branch = Branch(left, right, -1, -1, opcode)
                self.add(branch)
                return [branch]
            assert False, "unsupported comparison epxression"
        elif isinstance(e, OpExpr) and e.op in ['and', 'or']:
            if e.op == 'and':
                # Short circuit 'and' in a conditional context.
                lbranches = self.process_conditional(e.left)
                new = self.new_block()
                self.set_branches(lbranches, True, new)
                rbranches = self.process_conditional(e.right)
                return lbranches + rbranches
            else:
                # Short circuit 'or' in a conditional context.
                lbranches = self.process_conditional(e.left)
                new = self.new_block()
                self.set_branches(lbranches, False, new)
                rbranches = self.process_conditional(e.right)
                return lbranches + rbranches
        elif isinstance(e, UnaryExpr) and e.op == 'not':
            branches = self.process_conditional(e.expr)
            for b in branches:
                b.invert()
            return branches
        # Catch-all for arbitrary expressions.
        else:
            reg = self.accept(e)
            branch = Branch(reg, -1, -1, -1, Branch.BOOL_EXPR)
            self.add(branch)
            return [branch]

    def set_branches(self, branches: List[Branch], condition: bool,
                     target: BasicBlock) -> None:
        """Set branch targets for the given condition (True or False).

        If the target has already been set for a branch, skip the branch.
        """
        for b in branches:
            if condition:
                if b.true < 0:
                    b.true = target.label
            else:
                if b.false < 0:
                    b.false = target.label

    # Helpers

    def enter(self) -> None:
        self.environment = Environment()
        self.environments.append(self.environment)
        self.blocks.append([])
        self.new_block()

    def new_block(self) -> BasicBlock:
        new = BasicBlock(len(self.blocks[-1]))
        self.blocks[-1].append(new)
        return new

    def goto_new_block(self) -> BasicBlock:
        goto = Goto(-1)
        self.add(goto)
        block = self.new_block()
        goto.label = block.label
        return block

    def leave(self) -> Tuple[List[BasicBlock], Environment]:
        blocks = self.blocks.pop()
        env = self.environments.pop()
        self.environment = self.environments[-1]
        return blocks, env

    def add(self, op: Op) -> None:
        self.blocks[-1][-1].ops.append(op)

    def accept(self, node: Node, target: Register = -1) -> Register:
        self.targets.append(target)
        actual = node.accept(self)
        self.targets.pop()
        return actual

    def alloc_target(self, type: RTType) -> int:
        if self.targets[-1] < 0:
            return self.environment.add_temp(type)
        else:
            return self.targets[-1]

    def alloc_temp(self, type: RTType) -> int:
        return self.environment.add_temp(type)

    def box(self, src: Register, typ: RTType) -> Register:
        if typ.supports_unbox:
            target = self.alloc_temp(RTType('object'))
            self.add(Box(target, src, typ))
            return target
        else:
            # Already boxed
            return src

    def unbox(self, src: Register, target_type: RTType, target: Optional[Register] = None) -> Register:
        if target is None:
            target = self.alloc_temp(target_type)

        if target_type.supports_unbox:
            self.add(Unbox(target, src, target_type))
        else:
            self.add(Cast(target, src, target_type))
        return target

    def box_expr(self, expr: Expression) -> Register:
        typ = self.node_type(expr)
        return self.box(self.accept(expr), typ)
