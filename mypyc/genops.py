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
    Import, ImportFrom, ImportAll, DictExpr, StrExpr, CastExpr, TempNode, ARG_POS, MODULE_REF
)
from mypy.types import Type, Instance, CallableType, NoneTyp, TupleType, UnionType
from mypy.visitor import NodeVisitor
from mypy.subtypes import is_named_instance

from mypyc.ops import (
    BasicBlock, Environment, Op, LoadInt, RType, Register, Label, Return, FuncIR, Assign,
    Branch, Goto, RuntimeArg, Call, Box, Unbox, Cast, RTuple,
    Unreachable, TupleGet, TupleSet, ClassIR, RInstance, ModuleIR, GetAttr, SetAttr, LoadStatic,
    PyGetAttr, PyCall, ROptional, c_module_name, PyMethodCall, MethodCall, INVALID_REGISTER,
    INVALID_LABEL, int_rprimitive, is_int_rprimitive, bool_rprimitive, list_rprimitive,
    is_list_rprimitive, dict_rprimitive, is_dict_rprimitive, str_rprimitive, is_tuple_rprimitive,
    tuple_rprimitive, none_rprimitive, is_none_rprimitive, object_rprimitive, PrimitiveOp,
    ERR_FALSE, OpDescription
)
from mypyc.ops_primitive import binary_ops, unary_ops, func_ops, method_ops, name_ref_ops
from mypyc.ops_list import list_len_op, list_get_item_op, new_list_op
from mypyc.ops_dict import new_dict_op
from mypyc.ops_misc import none_op
from mypyc.subtype import is_subtype
from mypyc.sametype import is_same_type


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
                return int_rprimitive
            elif typ.type.fullname() == 'builtins.str':
                return str_rprimitive
            elif typ.type.fullname() == 'builtins.bool':
                return bool_rprimitive
            elif typ.type.fullname() == 'builtins.list':
                return list_rprimitive
            elif typ.type.fullname() == 'builtins.dict':
                return dict_rprimitive
            elif typ.type.fullname() == 'builtins.tuple':
                return tuple_rprimitive  # Varying-length tuple
            elif typ.type.fullname() == 'builtins.object':
                return object_rprimitive
            elif typ.type in self.type_to_ir:
                return RInstance(self.type_to_ir[typ.type])
        elif isinstance(typ, TupleType):
            return RTuple([self.type_to_rtype(t) for t in typ.items])
        elif isinstance(typ, CallableType):
            return object_rprimitive
        elif isinstance(typ, NoneTyp):
            return none_rprimitive
        elif isinstance(typ, UnionType):
            assert len(typ.items) == 2 and any(isinstance(it, NoneTyp) for it in typ.items)
            if isinstance(typ.items[0], NoneTyp):
                value_type = typ.items[1]
            else:
                value_type = typ.items[0]
            return ROptional(self.type_to_rtype(value_type))
        assert False, '%s unsupported' % type(typ)


class AssignmentTarget(object):
    pass


class AssignmentTargetRegister(AssignmentTarget):
    """Register as assignment target"""

    def __init__(self, register: Register) -> None:
        self.register = register


class AssignmentTargetIndex(AssignmentTarget):
    """base[index] as assignment target"""

    def __init__(self, base_reg: Register, index_reg: Register, rtype: RType) -> None:
        self.base_reg = base_reg
        self.index_reg = index_reg
        self.rtype = rtype


class AssignmentTargetAttr(AssignmentTarget):
    """obj.attr as assignment target"""

    def __init__(self, obj_reg: Register, attr: str, obj_type: RInstance) -> None:
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
        methods = []
        for name, node in cdef.info.names.items():
            if isinstance(node.node, Var):
                assert node.node.type, "Class member missing type"
                attributes.append((name, self.type_to_rtype(node.node.type)))
            elif isinstance(node.node, FuncDef):
                func = self.gen_func_def(node.node, cdef.name)
                self.functions.append(func)
                methods.append(func)
        ir = self.mapper.type_to_ir[cdef.info]
        ir.attributes = attributes
        ir.methods = methods
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

    def gen_func_def(self, fdef: FuncDef, class_name: Optional[str] = None) -> FuncIR:
        self.enter()

        for arg in fdef.arguments:
            assert arg.variable.type, "Function argument missing type"
            self.environment.add_local(arg.variable, self.type_to_rtype(arg.variable.type))
        self.ret_type = self.convert_return_type(fdef)
        fdef.body.accept(self)

        if is_none_rprimitive(self.ret_type):
            self.add_implicit_return()
        else:
            self.add_implicit_unreachable()

        blocks, env = self.leave()
        args = self.convert_args(fdef)
        return FuncIR(fdef.name(), class_name, args, self.ret_type, blocks, env)

    def visit_func_def(self, fdef: FuncDef) -> Register:
        self.functions.append(self.gen_func_def(fdef))
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
            retval = self.environment.add_temp(none_rprimitive)
            self.add(PrimitiveOp(retval, [], none_op, line=-1))
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
            retval = self.coerce(retval, self.node_type(stmt.expr), self.ret_type, stmt.line)
        else:
            retval = self.environment.add_temp(none_rprimitive)
            self.add(PrimitiveOp(retval, [], none_op, line=-1))
        self.add(Return(retval))
        return INVALID_REGISTER

    def visit_assignment_stmt(self, stmt: AssignmentStmt) -> Register:
        assert len(stmt.lvalues) == 1
        lvalue = stmt.lvalues[0]
        if stmt.type:
            lvalue_type = self.type_to_rtype(stmt.type)
            if isinstance(stmt.rvalue, TempNode):
                # This is actually a variable annotation without initializer. Don't generate
                # an assignment but we need to call get_assignment_target since it adds a
                # name binding as a side effect.
                self.get_assignment_target(lvalue, declare_new=True)
                return INVALID_REGISTER
        else:
            if isinstance(lvalue, IndexExpr):
                # TODO: This won't be right for user-defined classes. Store the
                #     lvalue type in mypy and remove this special case.
                lvalue_type = object_rprimitive
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
            if is_list_rprimitive(base_type) and is_int_rprimitive(index_type):
                # Indexed list set
                return AssignmentTargetIndex(base_reg, index_reg, base_type)
            elif is_dict_rprimitive(base_type):
                # Indexed dict set
                boxed_index = self.box(index_reg, index_type)
                return AssignmentTargetIndex(base_reg, boxed_index, base_type)
        elif isinstance(lvalue, MemberExpr):
            # Attribute assignment x.y = e
            obj_type = self.node_type(lvalue.expr)
            assert isinstance(obj_type, RInstance), 'Attribute set only supported for user types'
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
            target_reg = self.alloc_temp(bool_rprimitive)
            self.add(SetAttr(target_reg, target.obj_reg, target.attr, rvalue_reg, target.obj_type,
                             rvalue.line))
            return target_reg
        elif isinstance(target, AssignmentTargetIndex):
            item_reg = self.accept(rvalue)

            target_reg2 = self.translate_special_method_call(
                target.base_reg,
                '__setitem__',
                [target.index_reg, item_reg],
                None,
                rvalue.line,
                temp_result=True)
            if target_reg2 is not None:
                return target_reg2

            assert False, target.rtype

        assert False, 'Unsupported assignment target'

    def assign(self,
               lvalue: Lvalue,
               rvalue: Expression,
               rvalue_type: RType,
               lvalue_type: RType,
               declare_new: bool) -> Register:
        target = self.get_assignment_target(lvalue, declare_new)
        needs_box = rvalue_type.is_unboxed and not lvalue_type.is_unboxed
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
            index_reg = self.assign(s.index, IntExpr(0), int_rprimitive, int_rprimitive,
                                    declare_new=True)
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
            one_reg = self.alloc_temp(int_rprimitive)
            self.add(LoadInt(one_reg, 1))
            self.binary_op(int_rprimitive, index_reg, int_rprimitive, one_reg, '+', s.line,
                           target=index_reg)

            # Go back to loop condition check.
            self.add(Goto(top.label))
            next = self.new_block()
            self.set_branches(branches, False, next)

            self.pop_loop_stack(end_block, next)
            return INVALID_REGISTER

        if is_list_rprimitive(self.node_type(s.expr)):
            self.push_loop_stack()

            expr_reg = self.accept(s.expr)

            index_reg = self.alloc_temp(int_rprimitive)
            self.add(LoadInt(index_reg, 0))

            one_reg = self.alloc_temp(int_rprimitive)
            self.add(LoadInt(one_reg, 1))

            assert isinstance(s.index, NameExpr)
            assert isinstance(s.index.node, Var)
            lvalue_reg = self.environment.add_local(s.index.node, self.node_type(s.index))


            condition_block = self.goto_new_block()

            # For compatibility with python semantics we recalculate the length
            # at every iteration.
            len_reg = self.alloc_temp(int_rprimitive)
            self.add(PrimitiveOp(len_reg, [expr_reg], list_len_op, s.line))

            branch = Branch(index_reg, len_reg, INVALID_LABEL, INVALID_LABEL, Branch.INT_LT)
            self.add(branch)
            branches = [branch]

            body_block = self.new_block()
            self.set_branches(branches, True, body_block)

            target_list_type = self.types[s.expr]
            assert isinstance(target_list_type, Instance)
            target_type = self.type_to_rtype(target_list_type.args[0])
            value_box = self.alloc_temp(object_rprimitive)
            self.add(PrimitiveOp(value_box, [expr_reg, index_reg], list_get_item_op, s.line))

            self.unbox_or_cast(value_box, target_type, s.line, target=lvalue_reg)

            s.body.accept(self)

            end_block = self.goto_new_block()
            self.binary_op(int_rprimitive, index_reg, int_rprimitive, one_reg, '+', s.line,
                           target=index_reg)
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

    def visit_unary_expr(self, expr: UnaryExpr) -> Register:
        etype = self.node_type(expr.expr)
        ereg = self.accept(expr.expr)
        for desc in unary_ops.get(expr.op, []):
            if is_subtype(etype, desc.arg_types[0]):
                assert desc.result_type is not None
                target = self.alloc_target(desc.result_type)
                self.add(PrimitiveOp(target, [ereg], desc, expr.line))
                break
        else:
            # TODO: Fall back to generic C API
            assert False, 'Unsupported unary operation'

        return target

    def visit_op_expr(self, expr: OpExpr) -> Register:
        ltype = self.node_type(expr.left)
        rtype = self.node_type(expr.right)
        lreg = self.accept(expr.left)
        rreg = self.accept(expr.right)
        target = self.alloc_target(self.node_type(expr))
        return self.binary_op(ltype, lreg, rtype, rreg, expr.op, expr.line, target=target)

    def binary_op(self,
                  ltype: RType,
                  lreg: Register,
                  rtype: RType,
                  rreg: Register,
                  expr_op: str,
                  line: int,
                  target: Optional[Register] = None) -> Register:
        # Find the highest-priority primitive op that matches.
        matching = None  # type: Optional[OpDescription]
        for desc in binary_ops.get(expr_op, []):
            if (is_subtype(ltype, desc.arg_types[0])
                    and is_subtype(rtype, desc.arg_types[1])):
                if matching:
                    assert matching.priority != desc.priority, 'Ambiguous: %s, %s'  % (matching,
                                                                                       desc)
                    if desc.priority > matching.priority:
                        matching = desc
                else:
                    matching = desc
        if matching:
            return self.primitive_op(matching, [lreg, rreg], line, target)

        # TODO: Fall back to generic operation
        assert False, 'Unsupported binary operation'

    def visit_index_expr(self, expr: IndexExpr) -> Register:
        base_rtype = self.node_type(expr.base)
        base_reg = self.accept(expr.base)
        target_type = self.node_type(expr)

        if isinstance(base_rtype, RTuple):
            assert isinstance(expr.index, IntExpr)  # TODO
            target = self.alloc_target(target_type)
            self.add(TupleGet(target, base_reg, expr.index.value,
                              base_rtype.types[expr.index.value], expr.line))
            return target

        index_reg = self.accept(expr.index)
        target_reg = self.translate_special_method_call(
            base_reg,
            '__getitem__',
            [index_reg],
            self.node_type(expr),
            expr.line)
        if target_reg is not None:
            return target_reg

        assert False, 'Unsupported indexing operation'

    def visit_int_expr(self, expr: IntExpr) -> Register:
        reg = self.alloc_target(int_rprimitive)
        self.add(LoadInt(reg, expr.value))
        return reg

    def is_native_name_expr(self, expr: NameExpr) -> bool:
        # TODO later we want to support cross-module native calls too
        assert expr.node, "RefExpr not resolved"
        if '.' in expr.node.fullname():
            module_name = '.'.join(expr.node.fullname().split('.')[:-1])
            return module_name == self.current_module_name

        return True

    def visit_name_expr(self, expr: NameExpr) -> Register:
        assert expr.node, "RefExpr not resolved"
        fullname = expr.node.fullname()
        if fullname in name_ref_ops:
            # Use special access op for this particular name.
            desc = name_ref_ops[fullname]
            assert desc.result_type is not None
            target = self.alloc_target(desc.result_type)
            self.add(PrimitiveOp(target, [], desc, expr.line))
            return target

        if not self.is_native_name_expr(expr):
            return self.load_static_module_attr(expr)

        # TODO: We assume that this is a Var node, which is very limited
        assert isinstance(expr.node, Var)

        reg = self.environment.lookup(expr.node)
        return self.get_using_binder(reg, expr.node, expr)

    def get_using_binder(self, reg: Register, var: Var, expr: Expression) -> Register:
        assert var.type, "Variable missing type"
        var_type = self.type_to_rtype(var.type)
        target_type = self.node_type(expr)
        if var_type != target_type:
            # Cast/unbox to the narrower given by the binder.
            target = self.alloc_target(target_type)
            return self.unbox_or_cast(reg, target_type, expr.line, target)
        else:
            # Regular register access -- binder is not active.
            return reg

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
            assert isinstance(obj_type, RInstance), 'Attribute access not supported: %s' % obj_type
            self.add(GetAttr(target, obj_reg, expr.name, obj_type, expr.line))
            return target

    def load_static_module_attr(self, expr: RefExpr) -> Register:
        assert expr.node, "RefExpr not resolved"
        target = self.alloc_target(self.node_type(expr))
        module = '.'.join(expr.node.fullname().split('.')[:-1])
        right = expr.node.fullname().split('.')[-1]
        left = self.alloc_temp(object_rprimitive)
        self.add(LoadStatic(left, c_module_name(module)))
        self.add(PyGetAttr(target, left, right, expr.line))

        return target

    def py_call(self, function: Register, args: List[Register],
                target_type: RType, line: int) -> Register:
        target_box = self.alloc_temp(object_rprimitive)

        arg_boxes = [] # type: List[Register]
        for arg_reg in args:
            arg_boxes.append(self.box(arg_reg, self.environment.types[arg_reg]))

        self.add(PyCall(target_box, function, arg_boxes, line))
        return self.unbox_or_cast(target_box, target_type, line)

    def py_method_call(self,
                       obj: Register,
                       method: Register,
                       args: List[Register],
                       target_type: RType,
                       line: int) -> Register:
        target_box = self.alloc_temp(object_rprimitive)

        arg_boxes = [] # type: List[Register]
        for arg_reg in args:
            arg_boxes.append(self.box(arg_reg, self.environment.types[arg_reg]))

        self.add(PyMethodCall(target_box, obj, method, arg_boxes))
        return self.unbox_or_cast(target_box, target_type, line)

    def coerce_native_call_args(self,
                                args: List[Register],
                                callee_type: Type,
                                line: int) -> List[Register]:
        assert isinstance(callee_type, CallableType)
        # TODO: Argument kinds
        formal_arg_types = [self.type_to_rtype(t) for t in callee_type.arg_types]
        coerced_arg_regs = []
        for reg, arg_type in zip(args, formal_arg_types):
            typ = self.environment.types[reg]
            reg = self.coerce(reg, typ, arg_type, line)
            coerced_arg_regs.append(reg)
        return coerced_arg_regs


    def visit_call_expr(self, expr: CallExpr) -> Register:
        if isinstance(expr.analyzed, CastExpr):
            return self.translate_cast_expr(expr.analyzed)

        if isinstance(expr.callee, MemberExpr) and self.is_module_member_expr(expr.callee):
            # Fall back to a PyCall for module calls
                function = self.accept(expr.callee)
                args = [self.accept(arg) for arg in expr.args]
                return self.py_call(function, args, self.node_type(expr), expr.line)
        elif isinstance(expr.callee, MemberExpr):
            obj = self.accept(expr.callee.expr)
            args = [self.accept(arg) for arg in expr.args]
            assert expr.callee.expr in self.types
            receiver_rtype = self.node_type(expr.callee.expr)

            # First try to do a special-cased method call
            target = self.translate_special_method_call(
                obj, expr.callee.name, args, self.node_type(expr), expr.line)
            if target:
                return target

            # If the base type is one of ours, do a MethodCall, otherwise fall back
            # to a PyMethodCall
            if isinstance(receiver_rtype, RInstance):
                target = self.alloc_target(self.node_type(expr))
                arg_regs = self.coerce_native_call_args(
                    args, self.types[expr.callee], expr.line)
                self.add(MethodCall(target, obj, expr.callee.name,
                                    arg_regs, receiver_rtype, expr.line))
                return target
            else:
                method = self.load_static_unicode(expr.callee.name)
                return self.py_method_call(
                    obj, method, args, self.node_type(expr), expr.line)

        assert isinstance(expr.callee, NameExpr)  # TODO: Allow arbitrary callees

        # Gen the args
        fullname = expr.callee.fullname
        args = [self.accept(arg) for arg in expr.args]
        arg_types = [self.node_type(arg) for arg in expr.args]

        if fullname == 'builtins.len' and len(expr.args) == 1 and expr.arg_kinds == [ARG_POS]:
            expr_rtype = arg_types[0]
            if isinstance(expr_rtype, RTuple):
                # len() of fixed-length tuple can be trivially determined statically.
                target = self.alloc_target(int_rprimitive)
                self.add(LoadInt(target, len(expr_rtype.types)))
                return target

        # Handle data-driven special-cased primitive call ops.
        target_type = self.node_type(expr)
        if fullname is not None:
            for desc in func_ops.get(fullname, []):
                if len(args) == len(desc.arg_types) and expr.arg_kinds == [ARG_POS] * len(args):
                    for actual_arg, formal_arg in zip(arg_types, desc.arg_types):
                        if not is_subtype(actual_arg, formal_arg):
                            break
                    else:
                        target = self.alloc_target(target_type)
                        return self.primitive_op(desc, args, expr.line, target=target)

        fn = expr.callee.name  # TODO: fullname
        if not self.is_native_name_expr(expr.callee):
            # Python call
            function = self.accept(expr.callee)
            return self.py_call(function, args, target_type, expr.line)
        else:
            # Native call
            target = self.alloc_target(target_type)
            args = self.coerce_native_call_args(args, self.types[expr.callee], expr.line)
            self.add(Call(target, fn, args, expr.line))
        return target

    def translate_cast_expr(self, expr: CastExpr) -> Register:
        src = self.accept(expr.expr)
        target_type = self.type_to_rtype(expr.type)
        source_type = self.node_type(expr.expr)
        target = self.alloc_target(target_type)
        return self.coerce(src, source_type, target_type, expr.line, target=target)

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

    def translate_special_method_call(self,
                                      base_reg: Register,
                                      name: str,
                                      args: List[Register],
                                      result_type: Optional[RType],
                                      line: int,
                                      temp_result: bool = False) -> Optional[Register]:
        """Translate a method call which is handled nongenerically.

        These are special in the sense that we have code generated specifically for them.
        They tend to be method calls which have equivalents in C that are more direct
        than calling with the PyObject api.

        Return None if no translation found; otherwise return the target register.
        """
        base_type = self.environment.types[base_reg]
        arg_types = [self.environment.types[arg] for arg in args]
        fullname = '%s.%s' % (base_type.name, name)
        for desc in method_ops.get(fullname, []):
            if (is_subtype(base_type, desc.arg_types[0])
                    and len(arg_types) == len(desc.arg_types) - 1
                    and all(is_subtype(actual, formal)
                            for actual, formal in zip(arg_types, desc.arg_types[1:]))):
                # Found primitive call.
                coerced_args = []
                for arg, actual, formal in zip(args, arg_types, desc.arg_types[1:]):
                    reg = self.coerce(arg, actual, formal, line)
                    coerced_args.append(reg)
                if desc.result_type is None:
                    assert desc.error_kind == ERR_FALSE  # TODO: No-value ops not supported yet
                    result_type = bool_rprimitive
                    coercion = False
                elif result_type is None:
                    result_type = desc.result_type
                    coercion = False
                else:
                    coercion = not is_same_type(desc.result_type, result_type)
                if coercion:
                    assert desc.result_type is not None
                    op_target = self.alloc_temp(desc.result_type)
                if temp_result:
                    target = self.alloc_temp(result_type)
                else:
                    target = self.alloc_target(result_type)
                if not coercion:
                    op_target = target
                self.add(PrimitiveOp(op_target, [base_reg] + coerced_args, desc, line))
                if coercion:
                    assert desc.result_type is not None
                    self.coerce(op_target, desc.result_type, result_type, line, target=target)
                return target

        return None

    def visit_list_expr(self, expr: ListExpr) -> Register:
        items = [self.accept(item) for item in expr.items]
        target = self.alloc_target(list_rprimitive)
        return self.primitive_op(new_list_op, items, expr.line, target=target)

    def visit_tuple_expr(self, expr: TupleExpr) -> Register:
        tuple_type = self.node_type(expr)
        assert isinstance(tuple_type, RTuple)

        target = self.alloc_target(tuple_type)
        items = []
        for item_expr, item_type in zip(expr.items, tuple_type.types):
            reg = self.accept(item_expr)
            reg = self.coerce(reg, self.environment.types[reg], item_type, item_expr.line)
            items.append(reg)
        self.add(TupleSet(target, items, tuple_type, expr.line))
        return target

    def visit_dict_expr(self, expr: DictExpr) -> Register:
        assert not expr.items  # TODO
        target = self.alloc_target(dict_rprimitive)
        self.add(PrimitiveOp(target, [], new_dict_op, expr.line))
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
        return self.load_static_unicode(expr.value, self.cur_target())

    def process_conditional(self, e: Node) -> List[Branch]:
        if isinstance(e, ComparisonExpr):
            return self.process_comparison(e)
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

    def process_comparison(self, e: ComparisonExpr) -> List[Branch]:
        # TODO: Verify operand types.
        assert len(e.operators) == 1, 'more than 1 operator not supported'
        op = e.operators[0]
        if op in ['is', 'is not']:
            # Special case 'is' checks.
            # TODO: check if right operand is None
            left = self.accept(e.operands[0])
            branch = Branch(left, INVALID_REGISTER, INVALID_LABEL, INVALID_LABEL,
                            Branch.IS_NONE)
            if op == 'is not':
                branch.negated = True
        else:
            # General comparison -- evaluate both operands.
            left = self.accept(e.operands[0])
            ltype = self.node_type(e.operands[0])
            right = self.accept(e.operands[1])
            rtype = self.node_type(e.operands[1])
            if (op in ['==', '!=', '<', '<=', '>', '>=']
                    and is_same_type(ltype, int_rprimitive)
                    and is_same_type(rtype, int_rprimitive)):
                # Special op for int comparison.
                opcode = self.int_relative_ops[op]
                branch = Branch(left, right, INVALID_LABEL, INVALID_LABEL, opcode)
            else:
                # For other comparisons, generate a bool value and branch based on it. We need
                # this to handle exceptions in the comparison op.
                target = self.alloc_temp(self.node_type(e))
                if op in ['in', 'not in']:
                    self.binary_op(ltype, left, rtype, right, 'in', e.line, target=target)
                else:
                    self.binary_op(ltype, left, rtype, right, op, e.line, target=target)
                branch = Branch(target, INVALID_REGISTER, INVALID_LABEL, INVALID_LABEL,
                                Branch.BOOL_EXPR)
                if op == 'not in':
                    branch.negated = True
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

    def primitive_op(self, desc: OpDescription, args: List[Register], line: int,
                     target: Optional[Register] = None) -> Register:
        assert desc.result_type is not None
        coerced = []
        for i, arg in enumerate(args):
            formal_type = self.op_arg_type(desc, i)
            arg = self.coerce(arg, self.environment.types[arg], formal_type, line)
            coerced.append(arg)
        if target is None:
            target = self.alloc_temp(desc.result_type)
        target_type = self.reg_type(target)
        if is_same_type(target_type, desc.result_type):
            temp_target = target
        else:
            temp_target = self.alloc_temp(desc.result_type)
        self.add(PrimitiveOp(temp_target, coerced, desc, line))
        if target != temp_target:
            self.coerce(temp_target, desc.result_type, target_type, line, target=target)
        return target

    def op_arg_type(self, desc: OpDescription, n: int) -> RType:
        if n >= len(desc.arg_types):
            assert desc.is_var_arg
            return desc.arg_types[-1]
        return desc.arg_types[n]

    def accept(self, node: Node, target: Register = INVALID_REGISTER) -> Register:
        self.targets.append(target)
        actual = node.accept(self)
        self.targets.pop()
        if target != INVALID_REGISTER and target != actual:
            self.add(Assign(target, actual))

        return actual

    def cur_target(self) -> Register:
        return self.targets[-1]

    def alloc_target(self, type: RType) -> Register:
        """Get the current target, or if there is not a specified one, a temp"""
        # XXX: This is a somewhat dangerous method!
        # Only call it if you definitely own the target!
        # This means generally *not* in helper methods!
        return self.alloc_temp(type, self.cur_target())

    def alloc_temp(self, type: RType, target: Register = INVALID_REGISTER) -> Register:
        if target < 0:
            return self.environment.add_temp(type)
        else:
            return target

    def type_to_rtype(self, typ: Type) -> RType:
        return self.mapper.type_to_rtype(typ)

    def node_type(self, node: Expression) -> RType:
        if isinstance(node, IntExpr):
            # TODO: Don't special case IntExpr
            return int_rprimitive
        mypy_type = self.types[node]
        return self.type_to_rtype(mypy_type)

    def reg_type(self, reg: Register) -> RType:
        return self.environment.types[reg]

    def box(self, src: Register, typ: RType, target: Optional[Register] = None) -> Register:
        if typ.is_unboxed:
            if target is None:
                target = self.alloc_temp(object_rprimitive)
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

        if target_type.is_unboxed:
            self.add(Unbox(target, src, target_type, line))
        else:
            self.add(Cast(target, src, target_type, line))
        return target

    def box_expr(self, expr: Expression) -> Register:
        typ = self.node_type(expr)
        return self.box(self.accept(expr), typ)

    def load_static_unicode(self, value: str, target: Register = INVALID_REGISTER) -> Register:
        """Loads a static unicode value into a register.

        This is useful for more than just unicode literals; for example, method calls
        also require a PyObject * form for the name of the method.
        """
        if value not in self.unicode_literals:
            self.unicode_literals[value] = '__unicode_' + str(len(self.unicode_literals))
        static_symbol = self.unicode_literals[value]
        target = self.alloc_temp(str_rprimitive, target)
        self.add(LoadStatic(target, static_symbol))
        return target

    def coerce(self, src: Register, src_type: RType, target_type: RType, line: int,
               target: Optional[Register] = None) -> Register:
        """Generate a coercion/cast from one type to other (only if needed).

        For example, int -> object boxes the source int; int -> int emits nothing;
        object -> int unboxes the object. All conversions preserve object value.

        Returns the register with the converted value (may be same as src).
        """
        if src_type.is_unboxed and not target_type.is_unboxed:
            return self.box(src, src_type, target=target)
        if ((src_type.is_unboxed and target_type.is_unboxed)
                and not is_same_type(src_type, target_type)):
            # To go from one unboxed type to another, we go through a boxed
            # in-between value, for simplicity.
            tmp = self.box(src, src_type)
            return self.unbox_or_cast(tmp, target_type, line, target=target)
        if ((not src_type.is_unboxed and target_type.is_unboxed)
                or not is_subtype(src_type, target_type)):
            return self.unbox_or_cast(src, target_type, line, target=target)
        if target is None:
            return src
        else:
            self.add(Assign(target, src))
            return target
