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
    ContinueStmt, ConditionalExpr, OperatorAssignmentStmt, TupleExpr, ClassDef, TypeInfo,
    Import, ImportFrom, ImportAll, DictExpr, StrExpr, ARG_POS, MODULE_REF
)
from mypy.types import Type, Instance, CallableType, NoneTyp, TupleType, UnionType
from mypy.visitor import NodeVisitor
from mypy.subtypes import is_named_instance

from mypyc.ops import (
    BasicBlock, Environment, Op, LoadInt, RType, Register, Label, Return, FuncIR, Assign,
    PrimitiveOp, Branch, Goto, RuntimeArg, Call, Box, Unbox, Cast, TupleRType,
    Unreachable, TupleGet, ClassIR, UserRType, ModuleIR, GetAttr, SetAttr, LoadStatic,
    PyGetAttr, PyCall, IntRType, BoolRType, ListRType, SequenceTupleRType, ObjectRType, NoneRType,
    OptionalRType, DictRType, UnicodeRType, c_module_name, PyMethodCall,
    INVALID_REGISTER, INVALID_LABEL
)


def build_ir(module: MypyFile,
             types: Dict[Expression, Type]) -> ModuleIR:
    mapper = Mapper()
    builder = IRBuilder(types, mapper)
    module.accept(builder)

    return ModuleIR(builder.imports, builder.unicode_literals, builder.functions, builder.classes)


class Mapper:
    """Keep track of mappings from mypy AST to the IR."""

    def __init__(self) -> None:
        self.type_to_ir = {}  # type: Dict[TypeInfo, ClassIR]

    def type_to_rtype(self, typ: Type) -> RType:
        if isinstance(typ, Instance):
            if typ.type.fullname() == 'builtins.int':
                return IntRType()
            elif typ.type.fullname() == 'builtins.str':
                return UnicodeRType()
            elif typ.type.fullname() == 'builtins.bool':
                return BoolRType()
            elif typ.type.fullname() == 'builtins.list':
                return ListRType()
            elif typ.type.fullname() == 'builtins.dict':
                return DictRType()
            elif typ.type.fullname() == 'builtins.tuple':
                return SequenceTupleRType()
            elif typ.type in self.type_to_ir:
                return UserRType(self.type_to_ir[typ.type])
        elif isinstance(typ, TupleType):
            return TupleRType([self.type_to_rtype(t) for t in typ.items])
        elif isinstance(typ, CallableType):
            return ObjectRType()
        elif isinstance(typ, NoneTyp):
            return NoneRType()
        elif isinstance(typ, UnionType):
            assert len(typ.items) == 2 and any(isinstance(it, NoneTyp) for it in typ.items)
            if isinstance(typ.items[0], NoneTyp):
                value_type = typ.items[1]
            else:
                value_type = typ.items[0]
            return OptionalRType(self.type_to_rtype(value_type))
        assert False, '%s unsupported' % type(typ)


class AssignmentTarget(object):
    pass


class AssignmentTargetRegister(AssignmentTarget):
    def __init__(self, register: Register) -> None:
        self.register = register


class AssignmentTargetIndex(AssignmentTarget):
    def __init__(self, base_reg: Register, index_reg: Register, rtype: RType) -> None:
        self.base_reg = base_reg
        self.index_reg = index_reg
        self.rtype = rtype


class AssignmentTargetAttr(AssignmentTarget):
    def __init__(self, obj_reg: Register, attr: str, obj_type: UserRType) -> None:
        self.obj_reg = obj_reg
        self.attr = attr
        self.obj_type = obj_type


class IRBuilder(NodeVisitor[Register]):
    def __init__(self, types: Dict[Expression, Type], mapper: Mapper) -> None:
        self.types = types
        self.environment = Environment()
        self.environments = [self.environment]
        self.blocks = []  # type: List[List[BasicBlock]]
        self.functions = []  # type: List[FuncIR]
        self.classes = []  # type: List[ClassIR]
        self.targets = []  # type: List[Register]

        # These lists operate as stack frames for loops. Each loop adds a new
        # frame (i.e. adds a new empty list [] to the outermost list). Each
        # break or continue is inserted within that frame as they are visited
        # and at the end of the loop the stack is popped and any break/continue
        # gotos have their targets rewritten to the next basic block.
        self.break_gotos = []  # type: List[List[Goto]]
        self.continue_gotos = []  # type: List[List[Goto]]

        self.mapper = mapper
        self.imports = [] # type: List[str]

        # Maps unicode literals to the static c name for that literal
        self.unicode_literals = {} # type: Dict[str, str]

        self.current_module_name = None # type: Optional[str]

    def visit_mypy_file(self, mypyfile: MypyFile) -> Register:
        if mypyfile.fullname() in ('typing', 'abc'):
            # These module are special; their contents are currently all
            # built-in primitives.
            return INVALID_REGISTER

        # First pass: Build ClassIRs and TypeInfo-to-ClassIR mapping.
        for node in mypyfile.defs:
            if isinstance(node, ClassDef):
                self.prepare_class_def(node)

        # Second pass: Generate ops.
        self.current_module_name = mypyfile.fullname()
        for node in mypyfile.defs:
            node.accept(self)

        return INVALID_REGISTER

    def prepare_class_def(self, cdef: ClassDef) -> None:
        ir = ClassIR(cdef.name, [])  # Populate attributes later in visit_class_def
        self.classes.append(ir)
        self.mapper.type_to_ir[cdef.info] = ir

    def visit_class_def(self, cdef: ClassDef) -> Register:
        attributes = []
        for name, node in cdef.info.names.items():
            if isinstance(node.node, Var):
                attributes.append((name, self.type_to_rtype(node.node.type)))
        ir = self.mapper.type_to_ir[cdef.info]
        ir.attributes = attributes
        return INVALID_REGISTER

    def visit_import(self, node: Import) -> Register:
        if node.is_unreachable or node.is_mypy_only:
            pass
        if not node.is_top_level:
            assert False, "non-toplevel imports not supported"

        for node_id, _ in node.ids:
            self.imports.append(node_id)

        return INVALID_REGISTER

    def visit_import_from(self, node: ImportFrom) -> Register:
        if node.is_unreachable or node.is_mypy_only:
            pass
        if not node.is_top_level:
            assert False, "non-toplevel imports not supported"

        self.imports.append(node.id)

        return INVALID_REGISTER

    def visit_import_all(self, node: ImportAll) -> Register:
        if node.is_unreachable or node.is_mypy_only:
            pass
        if not node.is_top_level:
            assert False, "non-toplevel imports not supported"

        self.imports.append(node.id)

        return INVALID_REGISTER

    def visit_func_def(self, fdef: FuncDef) -> Register:
        self.enter()

        for arg in fdef.arguments:
            self.environment.add_local(arg.variable, self.type_to_rtype(arg.variable.type))
        fdef.body.accept(self)

        ret_type = self.convert_return_type(fdef)
        if ret_type.name == 'None':
            self.add_implicit_return()
        else:
            self.add_implicit_unreachable()

        blocks, env = self.leave()
        args = self.convert_args(fdef)
        func = FuncIR(fdef.name(), args, ret_type, blocks, env)
        self.functions.append(func)
        return INVALID_REGISTER

    def convert_args(self, fdef: FuncDef) -> List[RuntimeArg]:
        assert isinstance(fdef.type, CallableType)
        ann = fdef.type
        return [RuntimeArg(arg.variable.name(), self.type_to_rtype(ann.arg_types[i]))
                for i, arg in enumerate(fdef.arguments)]

    def convert_return_type(self, fdef: FuncDef) -> RType:
        assert isinstance(fdef.type, CallableType)
        return self.type_to_rtype(fdef.type.ret_type)

    def add_implicit_return(self) -> None:
        block = self.blocks[-1][-1]
        if not block.ops or not isinstance(block.ops[-1], Return):
            retval = self.environment.add_temp(NoneRType())
            self.add(PrimitiveOp(retval, PrimitiveOp.NONE, [], line=-1))
            self.add(Return(retval))

    def add_implicit_unreachable(self) -> None:
        block = self.blocks[-1][-1]
        if not block.ops or not isinstance(block.ops[-1], Return):
            self.add(Unreachable())

    def visit_block(self, block: Block) -> Register:
        for stmt in block.body:
            stmt.accept(self)
        return INVALID_REGISTER

    def visit_expression_stmt(self, stmt: ExpressionStmt) -> Register:
        self.accept(stmt.expr)
        return INVALID_REGISTER

    def visit_return_stmt(self, stmt: ReturnStmt) -> Register:
        if stmt.expr:
            retval = self.accept(stmt.expr)
        else:
            retval = self.environment.add_temp(NoneRType())
            self.add(PrimitiveOp(retval, PrimitiveOp.NONE, [], line=-1))
        self.add(Return(retval))
        return INVALID_REGISTER

    def visit_assignment_stmt(self, stmt: AssignmentStmt) -> Register:
        assert len(stmt.lvalues) == 1
        lvalue = stmt.lvalues[0]
        if stmt.type:
            lvalue_type = self.type_to_rtype(stmt.type)
        else:
            if isinstance(lvalue, IndexExpr):
                # TODO: This won't be right for user-defined classes. Store the
                #     lvalue type in mypy and remove this special case.
                lvalue_type = ObjectRType()
            else:
                lvalue_type = self.node_type(lvalue)
        rvalue_type = self.node_type(stmt.rvalue)
        return self.assign(lvalue, stmt.rvalue, rvalue_type, lvalue_type,
                           declare_new=(stmt.type is not None))

    def visit_operator_assignment_stmt(self, stmt: OperatorAssignmentStmt) -> Register:
        target = self.get_assignment_target(stmt.lvalue, declare_new=False)

        if isinstance(target, AssignmentTargetRegister):
            ltype = self.environment.types[target.register]
            rtype = self.node_type(stmt.rvalue)
            rreg = self.accept(stmt.rvalue)
            return self.binary_op(ltype, target.register, rtype, rreg, stmt.op, stmt.line,
                                  target=target.register)

        # NOTE: List index not supported yet for compound assignments.
        assert False, 'Unsupported lvalue: %r'

    def get_assignment_target(self, lvalue: Lvalue, declare_new: bool) -> AssignmentTarget:
        if isinstance(lvalue, NameExpr):
            # Assign to local variable.
            assert lvalue.kind == LDEF
            if lvalue.is_new_def or declare_new:
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
            base_reg = self.accept(lvalue.base)
            index_reg = self.accept(lvalue.index)
            if isinstance(base_type, ListRType) and isinstance(index_type, IntRType):
                # Indexed list set
                return AssignmentTargetIndex(base_reg, index_reg, base_type)
            elif isinstance(base_type, DictRType):
                # Indexed dict set
                boxed_index = self.box(index_reg, index_type)
                return AssignmentTargetIndex(base_reg, boxed_index, base_type)
        elif isinstance(lvalue, MemberExpr):
            # Attribute assignment x.y = e
            obj_type = self.node_type(lvalue.expr)
            assert isinstance(obj_type, UserRType), 'Attribute set only supported for user types'
            obj_reg = self.accept(lvalue.expr)
            return AssignmentTargetAttr(obj_reg, lvalue.name, obj_type)

        assert False, 'Unsupported lvalue: %r' % lvalue

    def assign_to_target(self,
            target: AssignmentTarget,
            rvalue: Expression,
            rvalue_type: RType,
            needs_box: bool) -> Register:
        rvalue_type = rvalue_type or self.node_type(rvalue)

        if isinstance(target, AssignmentTargetRegister):
            if needs_box:
                unboxed = self.accept(rvalue)
                return self.box(unboxed, rvalue_type, target=target.register)
            else:
                return self.accept(rvalue, target=target.register)
        elif isinstance(target, AssignmentTargetAttr):
            rvalue_reg = self.accept(rvalue)
            if needs_box:
                rvalue_reg = self.box(rvalue_reg, rvalue_type)
            target_reg = self.alloc_temp(BoolRType())
            self.add(SetAttr(target_reg, target.obj_reg, target.attr, rvalue_reg, target.obj_type,
                             rvalue.line))
            return target_reg
        elif isinstance(target, AssignmentTargetIndex):
            item_reg = self.accept(rvalue)
            boxed_item_reg = self.box(item_reg, rvalue_type)
            if isinstance(target.rtype, ListRType):
                op = PrimitiveOp.LIST_SET
            elif isinstance(target.rtype, DictRType):
                op = PrimitiveOp.DICT_SET
            else:
                assert False, target.rtype
            target_reg = self.alloc_temp(BoolRType())
            self.add(PrimitiveOp(target_reg, op,
                                 [target.base_reg, target.index_reg, boxed_item_reg], rvalue.line))
            return target_reg

        assert False, 'Unsupported assignment target'

    def assign(self,
               lvalue: Lvalue,
               rvalue: Expression,
               rvalue_type: RType,
               lvalue_type: RType,
               declare_new: bool) -> Register:
        target = self.get_assignment_target(lvalue, declare_new)
        needs_box = rvalue_type.supports_unbox and not lvalue_type.supports_unbox
        return self.assign_to_target(target, rvalue, rvalue_type, needs_box)

    def visit_if_stmt(self, stmt: IfStmt) -> Register:
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
        return INVALID_REGISTER

    def add_leave(self) -> Optional[Goto]:
        if not self.blocks[-1][-1].ops or not isinstance(self.blocks[-1][-1].ops[-1], Return):
            leave = Goto(INVALID_LABEL)
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

    def visit_while_stmt(self, s: WhileStmt) -> Register:
        self.push_loop_stack()

        # Split block so that we get a handle to the top of the loop.
        goto = Goto(INVALID_LABEL)
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
        return INVALID_REGISTER

    def visit_for_stmt(self, s: ForStmt) -> Register:
        if (isinstance(s.expr, CallExpr)
                and isinstance(s.expr.callee, RefExpr)
                and s.expr.callee.fullname == 'builtins.range'):
            self.push_loop_stack()

            # Special case for x in range(...)
            # TODO: Check argument counts and kinds; check the lvalue
            end = s.expr.args[0]
            end_reg = self.accept(end)

            # Initialize loop index to 0.
            index_reg = self.assign(s.index, IntExpr(0), IntRType(), IntRType(), declare_new=True)
            goto = Goto(INVALID_LABEL)
            self.add(goto)

            # Add loop condition check.
            top = self.new_block()
            goto.label = top.label
            branch = Branch(index_reg, end_reg, INVALID_LABEL, INVALID_LABEL, Branch.INT_LT)
            self.add(branch)
            branches = [branch]

            body = self.new_block()
            self.set_branches(branches, True, body)
            s.body.accept(self)

            end_goto = Goto(INVALID_LABEL)
            self.add(end_goto)
            end_block = self.new_block()
            end_goto.label = end_block.label

            # Increment index register.
            one_reg = self.alloc_temp(IntRType())
            self.add(LoadInt(one_reg, 1))
            self.add(PrimitiveOp(index_reg, PrimitiveOp.INT_ADD, [index_reg, one_reg], s.line))

            # Go back to loop condition check.
            self.add(Goto(top.label))
            next = self.new_block()
            self.set_branches(branches, False, next)

            self.pop_loop_stack(end_block, next)
            return INVALID_REGISTER

        if self.node_type(s.expr).name == 'list':
            self.push_loop_stack()

            expr_reg = self.accept(s.expr)

            index_reg = self.alloc_temp(IntRType())
            self.add(LoadInt(index_reg, 0))

            one_reg = self.alloc_temp(IntRType())
            self.add(LoadInt(one_reg, 1))

            assert isinstance(s.index, NameExpr)
            assert isinstance(s.index.node, Var)
            lvalue_reg = self.environment.add_local(s.index.node, self.node_type(s.index))


            condition_block = self.goto_new_block()

            # For compatibility with python semantics we recalculate the length
            # at every iteration.
            len_reg = self.alloc_temp(IntRType())
            self.add(PrimitiveOp(len_reg, PrimitiveOp.LIST_LEN, [expr_reg], s.line))

            branch = Branch(index_reg, len_reg, INVALID_LABEL, INVALID_LABEL, Branch.INT_LT)
            self.add(branch)
            branches = [branch]

            body_block = self.new_block()
            self.set_branches(branches, True, body_block)

            target_list_type = self.types[s.expr]
            assert isinstance(target_list_type, Instance)
            target_type = self.type_to_rtype(target_list_type.args[0])
            value_box = self.alloc_temp(ObjectRType())
            self.add(PrimitiveOp(value_box, PrimitiveOp.LIST_GET, [expr_reg, index_reg], s.line))

            self.unbox_or_cast(value_box, target_type, s.line, target=lvalue_reg)

            s.body.accept(self)

            end_block = self.goto_new_block()
            self.add(PrimitiveOp(index_reg, PrimitiveOp.INT_ADD, [index_reg, one_reg], s.line))
            self.add(Goto(condition_block.label))

            next_block = self.new_block()
            self.set_branches(branches, False, next_block)

            self.pop_loop_stack(end_block, next_block)

            return INVALID_REGISTER

        assert False, 'for not supported'

    def visit_break_stmt(self, node: BreakStmt) -> Register:
        self.break_gotos[-1].append(Goto(INVALID_LABEL))
        self.add(self.break_gotos[-1][-1])
        return INVALID_REGISTER

    def visit_continue_stmt(self, node: ContinueStmt) -> Register:
        self.continue_gotos[-1].append(Goto(INVALID_LABEL))
        self.add(self.continue_gotos[-1][-1])
        return INVALID_REGISTER

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

    def visit_unary_expr(self, expr: UnaryExpr) -> Register:
        if expr.op != '-':
            assert False, 'Unsupported unary operation'

        etype = self.node_type(expr.expr)
        reg = self.accept(expr.expr)
        if etype.name != 'int':
            assert False, 'Unsupported unary operation'

        target = self.alloc_target(IntRType())
        zero = self.accept(IntExpr(0))
        self.add(PrimitiveOp(target, PrimitiveOp.INT_SUB, [zero, reg], expr.line))

        return target

    def visit_op_expr(self, expr: OpExpr) -> Register:
        ltype = self.node_type(expr.left)
        rtype = self.node_type(expr.right)
        lreg = self.accept(expr.left)
        rreg = self.accept(expr.right)
        return self.binary_op(ltype, lreg, rtype, rreg, expr.op, expr.line)

    def binary_op(self, ltype: RType, lreg: Register, rtype: RType, rreg: Register, expr_op: str,
                  line: int, target: Optional[Register] = None) -> Register:
        if ltype.name == 'int' and rtype.name == 'int':
            # Primitive int operation
            if target is None:
                target = self.alloc_target(IntRType())
            op = self.int_binary_ops[expr_op]
        elif (ltype.name == 'list' or rtype.name == 'list') and expr_op == '*':
            if rtype.name == 'list':
                ltype, rtype = rtype, ltype
                lreg, rreg = rreg, lreg
            if rtype.name != 'int':
                assert False, 'Unsupported binary operation'  # TODO: Operator overloading
            if target is None:
                target = self.alloc_target(ListRType())
            op = PrimitiveOp.LIST_REPEAT
        elif isinstance(rtype, DictRType):
            if expr_op == 'in':
                if target is None:
                    target = self.alloc_target(BoolRType())
                lreg = self.box(lreg, ltype)
                op = PrimitiveOp.DICT_CONTAINS
            else:
                assert False, 'Unsupported binary operation'
        else:
            assert False, 'Unsupported binary operation'
        self.add(PrimitiveOp(target, op, [lreg, rreg], line))
        return target

    def visit_index_expr(self, expr: IndexExpr) -> Register:
        base_rtype = self.node_type(expr.base)
        base_reg = self.accept(expr.base)
        target_type = self.node_type(expr)

        if isinstance(base_rtype, (ListRType, SequenceTupleRType, DictRType)):
            index_type = self.node_type(expr.index)
            if not isinstance(base_rtype, DictRType):
                assert isinstance(index_type, IntRType), 'Unsupported indexing operation'  # TODO
            if isinstance(base_rtype, ListRType):
                op = PrimitiveOp.LIST_GET
            elif isinstance(base_rtype, DictRType):
                op = PrimitiveOp.DICT_GET
            else:
                op = PrimitiveOp.HOMOGENOUS_TUPLE_GET
            index_reg = self.accept(expr.index)
            if isinstance(base_rtype, DictRType):
                index_reg = self.box(index_reg, index_type)
            tmp = self.alloc_temp(ObjectRType())
            self.add(PrimitiveOp(tmp, op, [base_reg, index_reg], expr.line))
            target = self.alloc_target(target_type)
            return self.unbox_or_cast(tmp, target_type, expr.line, target)
        elif isinstance(base_rtype, TupleRType):
            assert isinstance(expr.index, IntExpr)  # TODO
            target = self.alloc_target(target_type)
            self.add(TupleGet(target, base_reg, expr.index.value,
                              base_rtype.types[expr.index.value], expr.line))
            return target

        assert False, 'Unsupported indexing operation'

    def visit_int_expr(self, expr: IntExpr) -> Register:
        reg = self.alloc_target(IntRType())
        self.add(LoadInt(reg, expr.value))
        return reg

    def is_native_name_expr(self, expr: NameExpr) -> bool:
        # TODO later we want to support cross-module native calls too
        if '.' in expr.node.fullname():
            module_name = '.'.join(expr.node.fullname().split('.')[:-1])
            return module_name == self.current_module_name

        return True

    def visit_name_expr(self, expr: NameExpr) -> Register:
        if expr.node.fullname() == 'builtins.None':
            target = self.alloc_target(NoneRType())
            self.add(PrimitiveOp(target, PrimitiveOp.NONE, [], expr.line))
            return target
        elif expr.node.fullname() == 'builtins.True':
            target = self.alloc_target(BoolRType())
            self.add(PrimitiveOp(target, PrimitiveOp.TRUE, [], expr.line))
            return target
        elif expr.node.fullname() == 'builtins.False':
            target = self.alloc_target(BoolRType())
            self.add(PrimitiveOp(target, PrimitiveOp.FALSE, [], expr.line))
            return target

        if not self.is_native_name_expr(expr):
            return self.load_static_module_attr(expr)

        # TODO: We assume that this is a Var node, which is very limited
        assert isinstance(expr.node, Var)

        reg = self.environment.lookup(expr.node)
        return self.get_using_binder(reg, expr.node, expr)

    def get_using_binder(self, reg: Register, var: Var, expr: Expression) -> Register:
        var_type = self.type_to_rtype(var.type)
        target_type = self.node_type(expr)
        if var_type != target_type:
            # Cast/unbox to the narrower given by the binder.
            if self.targets[-1] < 0:
                target = self.alloc_temp(target_type)
            else:
                target = self.targets[-1]
            return self.unbox_or_cast(reg, target_type, expr.line, target)
        else:
            # Regular register access -- binder is not active.
            if self.targets[-1] < 0:
                return reg
            else:
                target = self.targets[-1]
                self.add(Assign(target, reg))
                return target

    def is_module_member_expr(self, expr: MemberExpr) -> bool:
        return isinstance(expr.expr, RefExpr) and expr.expr.kind == MODULE_REF

    def visit_member_expr(self, expr: MemberExpr) -> Register:
        if self.is_module_member_expr(expr):
            return self.load_static_module_attr(expr)

        else:
            obj_reg = self.accept(expr.expr)
            attr_type = self.node_type(expr)
            target = self.alloc_target(attr_type)
            obj_type = self.node_type(expr.expr)
            assert isinstance(obj_type,
                              UserRType), 'Attribute access not supported: %s' % obj_type
            self.add(GetAttr(target, obj_reg, expr.name, obj_type, expr.line))
            return target

    def load_static_module_attr(self, expr: RefExpr) -> Register:
        target = self.alloc_target(self.node_type(expr))
        module = '.'.join(expr.node.fullname().split('.')[:-1])
        right = expr.node.fullname().split('.')[-1]
        left = self.alloc_temp(ObjectRType())
        self.add(LoadStatic(left, c_module_name(module)))
        self.add(PyGetAttr(target, left, right, expr.line))

        return target

    def py_call(self, function: Register, args: List[Expression], target_type: RType,
                line: int) -> Register:
        target_box = self.alloc_temp(ObjectRType())

        arg_boxes = [] # type: List[Register]
        for arg_expr in args:
            arg_reg = self.accept(arg_expr)
            arg_boxes.append(self.box(arg_reg, self.node_type(arg_expr)))

        self.add(PyCall(target_box, function, arg_boxes, line))
        return self.unbox_or_cast(target_box, target_type, line)

    def py_method_call(self,
                       obj: Register,
                       method: Register,
                       args: List[Expression],
                       target_type: RType,
                       line: int) -> Register:
        target_box = self.alloc_temp(ObjectRType())

        arg_boxes = [] # type: List[Register]
        for arg_expr in args:
            arg_reg = self.accept(arg_expr)
            arg_boxes.append(self.box(arg_reg, self.node_type(arg_expr)))

        self.add(PyMethodCall(target_box, obj, method, arg_boxes))
        return self.unbox_or_cast(target_box, target_type, line)

    def visit_call_expr(self, expr: CallExpr) -> Register:
        if isinstance(expr.callee, MemberExpr):
            is_module_call = self.is_module_member_expr(expr.callee)
            if expr.callee.expr in self.types and not is_module_call:
                target = self.translate_special_method_call(expr.callee, expr)
                if target:
                    return target

            # Either its a module call or translating to a special method call failed, so we have
            # to fallback to a PyCall
            if is_module_call:
                function = self.accept(expr.callee)
                return self.py_call(function, expr.args, self.node_type(expr), expr.line)
            else:
                assert expr.callee.expr in self.types
                obj = self.accept(expr.callee.expr)
                method = self.load_static_unicode(expr.callee.name)
                return self.py_method_call(obj, method, expr.args, self.node_type(expr), expr.line)

        assert isinstance(expr.callee, NameExpr)
        fn = expr.callee.name  # TODO: fullname
        if fn == 'len' and len(expr.args) == 1 and expr.arg_kinds == [ARG_POS]:
            target = self.alloc_target(IntRType())
            arg = self.accept(expr.args[0])

            expr_rtype = self.node_type(expr.args[0])
            if expr_rtype.name == 'list':
                self.add(PrimitiveOp(target, PrimitiveOp.LIST_LEN, [arg], expr.line))
            elif expr_rtype.name == 'sequence_tuple':
                self.add(PrimitiveOp(target, PrimitiveOp.HOMOGENOUS_TUPLE_LEN, [arg], expr.line))
            elif isinstance(expr_rtype, TupleRType):
                self.add(LoadInt(target, len(expr_rtype.types)))
            else:
                assert False, "unsupported use of len"

        # Handle conversion to sequence tuple
        elif fn == 'tuple' and len(expr.args) == 1 and expr.arg_kinds == [ARG_POS]:
            target = self.alloc_target(SequenceTupleRType())
            arg = self.accept(expr.args[0])

            self.add(PrimitiveOp(target, PrimitiveOp.LIST_TO_HOMOGENOUS_TUPLE, [arg], expr.line))
        else:
            target_type = self.node_type(expr)
            if not(self.is_native_name_expr(expr.callee)):
                function = self.accept(expr.callee)
                return self.py_call(function, expr.args, target_type, expr.line)

            target = self.alloc_target(target_type)
            args = [self.accept(arg) for arg in expr.args]
            self.add(Call(target, fn, args, expr.line))
        return target

    def visit_conditional_expr(self, expr: ConditionalExpr) -> Register:
        branches = self.process_conditional(expr.cond)
        target = self.alloc_target(self.node_type(expr))

        if_body = self.new_block()
        self.set_branches(branches, True, if_body)
        self.accept(expr.if_expr, target=target)
        if_goto_next = Goto(INVALID_LABEL)
        self.add(if_goto_next)

        else_body = self.new_block()
        self.set_branches(branches, False, else_body)
        self.accept(expr.else_expr, target=target)
        else_goto_next = Goto(INVALID_LABEL)
        self.add(else_goto_next)

        next = self.new_block()
        if_goto_next.label = next.label
        else_goto_next.label = next.label

        return target

    def translate_special_method_call(self, callee: MemberExpr, expr: CallExpr) -> Optional[Register]:
        """Translate a method call which is handled nongenerically.

        These are special in the sense that we have code generated specifically for them.
        They tend to be method calls which have equivalents in C that are more direct
        than calling with the PyObject api.
        """
        base_type = self.node_type(callee.expr)
        result_type = self.node_type(expr)
        base = self.accept(callee.expr)
        if callee.name == 'append' and base_type.name == 'list':
            target = self.alloc_target(BoolRType())
            arg = self.box_expr(expr.args[0])
            self.add(PrimitiveOp(target, PrimitiveOp.LIST_APPEND, [base, arg], expr.line))
        elif callee.name == 'update' and base_type.name == 'dict':
            target = self.alloc_target(BoolRType())
            other_list_reg = self.accept(expr.args[0])
            self.add(PrimitiveOp(target, PrimitiveOp.DICT_UPDATE, [base, other_list_reg],
                                 expr.line))
        else:
            return None
        return target

    def visit_list_expr(self, expr: ListExpr) -> Register:
        list_type = self.types[expr]
        assert isinstance(list_type, Instance)
        item_type = self.type_to_rtype(list_type.args[0])
        target = self.alloc_target(ListRType())
        items = []
        for item in expr.items:
            item_reg = self.accept(item)
            boxed = self.box(item_reg, item_type)
            items.append(boxed)
        self.add(PrimitiveOp(target, PrimitiveOp.NEW_LIST, items, expr.line))
        return target

    def visit_tuple_expr(self, expr: TupleExpr) -> Register:
        tuple_type = self.types[expr]
        assert isinstance(tuple_type, TupleType)

        target = self.alloc_target(self.type_to_rtype(tuple_type))
        items = [self.accept(i) for i in expr.items]
        self.add(PrimitiveOp(target, PrimitiveOp.NEW_TUPLE, items, expr.line))
        return target

    def visit_dict_expr(self, expr: DictExpr) -> Register:
        assert not expr.items  # TODO
        target = self.alloc_target(DictRType())
        self.add(PrimitiveOp(target, PrimitiveOp.NEW_DICT, [], expr.line))
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

    def visit_str_expr(self, expr: StrExpr) -> Register:
        return self.load_static_unicode(expr.value)

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
                branch = Branch(left, right, INVALID_LABEL, INVALID_LABEL, opcode)
            elif op in ['is', 'is not']:
                # TODO: check if right operand is None
                left = self.accept(e.operands[0])
                branch = Branch(left, INVALID_REGISTER, INVALID_LABEL, INVALID_LABEL,
                                Branch.IS_NONE)
                if op == 'is not':
                    branch.negated = True
            elif op in ['in', 'not in']:
                left = self.accept(e.operands[0])
                ltype = self.node_type(e.operands[0])
                right = self.accept(e.operands[1])
                rtype = self.node_type(e.operands[1])
                target = self.alloc_temp(self.node_type(e))
                self.binary_op(ltype, left, rtype, right, 'in', e.line, target=target)
                branch = Branch(target, INVALID_REGISTER, INVALID_LABEL, INVALID_LABEL,
                                Branch.BOOL_EXPR)
                if op == 'not in':
                    branch.negated = True
            else:
                assert False, "unsupported comparison epxression"
            self.add(branch)
            return [branch]
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
            branch = Branch(reg, INVALID_REGISTER, INVALID_LABEL, INVALID_LABEL, Branch.BOOL_EXPR)
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
        new = BasicBlock(Label(len(self.blocks[-1])))
        self.blocks[-1].append(new)
        return new

    def goto_new_block(self) -> BasicBlock:
        goto = Goto(INVALID_LABEL)
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

    def accept(self, node: Node, target: Register = INVALID_REGISTER) -> Register:
        self.targets.append(target)
        actual = node.accept(self)
        self.targets.pop()
        return actual

    def alloc_target(self, type: RType) -> Register:
        if self.targets[-1] < 0:
            return self.environment.add_temp(type)
        else:
            return self.targets[-1]

    def alloc_temp(self, type: RType) -> Register:
        return self.environment.add_temp(type)

    def type_to_rtype(self, typ: Type) -> RType:
        return self.mapper.type_to_rtype(typ)

    def node_type(self, node: Expression) -> RType:
        mypy_type = self.types[node]
        return self.type_to_rtype(mypy_type)

    def box(self, src: Register, typ: RType, target: Optional[Register] = None) -> Register:
        if typ.supports_unbox:
            if target is None:
                target = self.alloc_temp(ObjectRType())
            self.add(Box(target, src, typ))
            return target
        else:
            # Already boxed
            if target is not None:
                self.add(Assign(target, src))
                return target
            else:
                return src

    def unbox_or_cast(self, src: Register, target_type: RType, line: int,
                      target: Optional[Register] = None) -> Register:
        if target is None:
            target = self.alloc_temp(target_type)

        if target_type.supports_unbox:
            self.add(Unbox(target, src, target_type, line))
        else:
            self.add(Cast(target, src, target_type, line))
        return target

    def box_expr(self, expr: Expression) -> Register:
        typ = self.node_type(expr)
        return self.box(self.accept(expr), typ)

    def load_static_unicode(self, value: str) -> Register:
        """Loads a static unicode value into a register.

        This is useful for more than just unicode literals; for example, method calls
        also require a PyObject * form for the name of the method.
        """
        if value not in self.unicode_literals:
            self.unicode_literals[value] = '__unicode_' + str(len(self.unicode_literals))
        static_symbol = self.unicode_literals[value]
        target = self.alloc_target(UnicodeRType())
        self.add(LoadStatic(target, static_symbol))
        return target
