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
    IfStmt, UnaryExpr, ComparisonExpr, WhileStmt, Argument, CallExpr, IndexExpr, Block,
    Expression, ListExpr, ExpressionStmt, MemberExpr, ForStmt, RefExpr, Lvalue, BreakStmt,
    ContinueStmt, ConditionalExpr, OperatorAssignmentStmt, TupleExpr, ClassDef, TypeInfo,
    Import, ImportFrom, ImportAll, DictExpr, StrExpr, CastExpr, TempNode, ARG_POS, MODULE_REF
)
from mypy.types import Type, Instance, CallableType, NoneTyp, TupleType, UnionType
from mypy.visitor import NodeVisitor
from mypy.subtypes import is_named_instance

from mypyc.ops import (
    BasicBlock, Environment, Op, LoadInt, RType, Value, Register, Label, Return, FuncIR,
    Assign,
    Branch, Goto, RuntimeArg, Call, Box, Unbox, Cast, RTuple,
    Unreachable, TupleGet, TupleSet, ClassIR, RInstance, ModuleIR, GetAttr, SetAttr, LoadStatic,
    PyGetAttr, PyCall, ROptional, c_module_name, PyMethodCall, MethodCall, INVALID_VALUE,
    INVALID_LABEL, int_rprimitive, is_int_rprimitive, bool_rprimitive, list_rprimitive,
    is_list_rprimitive, dict_rprimitive, is_dict_rprimitive, str_rprimitive, is_tuple_rprimitive,
    tuple_rprimitive, none_rprimitive, is_none_rprimitive, object_rprimitive, PrimitiveOp,
    ERR_FALSE, OpDescription, RegisterOp,
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
    type = None  # type: RType


class AssignmentTargetRegister(AssignmentTarget):
    """Register as assignment target"""

    def __init__(self, register: Register) -> None:
        self.register = register
        self.type = register.type


class AssignmentTargetIndex(AssignmentTarget):
    """base[index] as assignment target"""

    def __init__(self, base: Value, index: Value) -> None:
        self.base = base
        self.index = index
        # TODO: This won't be right for user-defined classes. Store the
        #       lvalue type in mypy and remove this special case.
        self.type = object_rprimitive


class AssignmentTargetAttr(AssignmentTarget):
    """obj.attr as assignment target"""

    def __init__(self, obj: Value, attr: str) -> None:
        self.obj = obj
        self.attr = attr
        assert isinstance(obj.type, RInstance), 'Attribute set only supported for user types'
        self.obj_type = obj.type
        self.type = obj.type.attr_type(attr)


class IRBuilder(NodeVisitor[Value]):
    def __init__(self, types: Dict[Expression, Type], mapper: Mapper) -> None:
        self.types = types
        self.environment = Environment()
        self.environments = [self.environment]
        self.blocks = []  # type: List[List[BasicBlock]]
        self.functions = []  # type: List[FuncIR]
        self.classes = []  # type: List[ClassIR]

        # These lists operate as stack frames for loops. Each loop adds a new
        # frame (i.e. adds a new empty list [] to the outermost list). Each
        # break or continue is inserted within that frame as they are visited
        # and at the end of the loop the stack is popped and any break/continue
        # gotos have their targets rewritten to the next basic block.
        self.break_gotos = []  # type: List[List[Goto]]
        self.continue_gotos = []  # type: List[List[Goto]]

        self.mapper = mapper
        self.imports = []  # type: List[str]

        # Maps unicode literals to the static c name for that literal
        self.unicode_literals = {}  # type: Dict[str, str]

        self.current_module_name = None  # type: Optional[str]

    def visit_mypy_file(self, mypyfile: MypyFile) -> Value:
        if mypyfile.fullname() in ('typing', 'abc'):
            # These module are special; their contents are currently all
            # built-in primitives.
            return INVALID_VALUE

        # First pass: Build ClassIRs and TypeInfo-to-ClassIR mapping.
        for node in mypyfile.defs:
            if isinstance(node, ClassDef):
                self.prepare_class_def(node)

        # Second pass: Generate ops.
        self.current_module_name = mypyfile.fullname()
        for node in mypyfile.defs:
            node.accept(self)

        return INVALID_VALUE

    def prepare_class_def(self, cdef: ClassDef) -> None:
        # We want to collect the attributes first so they are available
        # while generating the methods
        ir = ClassIR(cdef.name)
        self.classes.append(ir)
        self.mapper.type_to_ir[cdef.info] = ir

        for name, node in cdef.info.names.items():
            if isinstance(node.node, Var):
                assert node.node.type, "Class member missing type"
                ir.attributes.append((name, self.type_to_rtype(node.node.type)))

    def visit_class_def(self, cdef: ClassDef) -> Value:
        ir = self.mapper.type_to_ir[cdef.info]
        for name, node in cdef.info.names.items():
            if isinstance(node.node, FuncDef):
                func = self.gen_func_def(node.node, cdef.name)
                self.functions.append(func)
                ir.methods.append(func)
        return INVALID_VALUE

    def visit_import(self, node: Import) -> Value:
        if node.is_unreachable or node.is_mypy_only:
            pass
        if not node.is_top_level:
            assert False, "non-toplevel imports not supported"

        for node_id, _ in node.ids:
            self.imports.append(node_id)

        return INVALID_VALUE

    def visit_import_from(self, node: ImportFrom) -> Value:
        if node.is_unreachable or node.is_mypy_only:
            pass
        if not node.is_top_level:
            assert False, "non-toplevel imports not supported"

        self.imports.append(node.id)

        return INVALID_VALUE

    def visit_import_all(self, node: ImportAll) -> Value:
        if node.is_unreachable or node.is_mypy_only:
            pass
        if not node.is_top_level:
            assert False, "non-toplevel imports not supported"

        self.imports.append(node.id)

        return INVALID_VALUE

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

    def visit_func_def(self, fdef: FuncDef) -> Value:
        self.functions.append(self.gen_func_def(fdef))
        return INVALID_VALUE

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
            retval = self.add(PrimitiveOp([], none_op, line=-1))
            self.add(Return(retval))

    def add_implicit_unreachable(self) -> None:
        block = self.blocks[-1][-1]
        if not block.ops or not isinstance(block.ops[-1], Return):
            self.add(Unreachable())

    def visit_block(self, block: Block) -> Value:
        for stmt in block.body:
            stmt.accept(self)
        return INVALID_VALUE

    def visit_expression_stmt(self, stmt: ExpressionStmt) -> Value:
        self.accept(stmt.expr)
        return INVALID_VALUE

    def visit_return_stmt(self, stmt: ReturnStmt) -> Value:
        if stmt.expr:
            retval = self.accept(stmt.expr)
            retval = self.coerce(retval, self.ret_type, stmt.line)
        else:
            retval = self.add(PrimitiveOp([], none_op, line=-1))
        self.add(Return(retval))
        return INVALID_VALUE

    def visit_assignment_stmt(self, stmt: AssignmentStmt) -> Value:
        assert len(stmt.lvalues) == 1
        lvalue = stmt.lvalues[0]
        if stmt.type and isinstance(stmt.rvalue, TempNode):
            # This is actually a variable annotation without initializer. Don't generate
            # an assignment but we need to call get_assignment_target since it adds a
            # name binding as a side effect.
            self.get_assignment_target(lvalue)
            return INVALID_VALUE
        self.assign(lvalue, stmt.rvalue)
        return INVALID_VALUE

    def visit_operator_assignment_stmt(self, stmt: OperatorAssignmentStmt) -> Value:
        target = self.get_assignment_target(stmt.lvalue)

        if isinstance(target, AssignmentTargetRegister):
            rreg = self.accept(stmt.rvalue)
            res = self.binary_op(target.register, rreg, stmt.op, stmt.line)
            self.add(Assign(target.register, res))
            return INVALID_VALUE

        # NOTE: List index not supported yet for compound assignments.
        assert False, 'Unsupported lvalue: %r'

    def get_assignment_target(self, lvalue: Lvalue) -> AssignmentTarget:
        if isinstance(lvalue, NameExpr):
            # Assign to local variable.
            assert lvalue.kind == LDEF
            assert isinstance(lvalue.node, Var)  # TODO: Can this fail?
            if lvalue.node not in self.environment.symtable:
                # Define a new variable.
                lvalue_reg = self.environment.add_local(lvalue.node, self.node_type(lvalue))
            else:
                # Assign to a previously defined variable.
                lvalue_reg = self.environment.lookup(lvalue.node)

            return AssignmentTargetRegister(lvalue_reg)
        elif isinstance(lvalue, IndexExpr):
            # Indexed assignment x[y] = e
            base = self.accept(lvalue.base)
            index = self.accept(lvalue.index)
            if is_list_rprimitive(base.type) and is_int_rprimitive(index.type):
                # Indexed list set
                return AssignmentTargetIndex(base, index)
            elif is_dict_rprimitive(base.type):
                # Indexed dict set
                boxed_index = self.box(index)
                return AssignmentTargetIndex(base, boxed_index)
        elif isinstance(lvalue, MemberExpr):
            # Attribute assignment x.y = e
            obj = self.accept(lvalue.expr)
            return AssignmentTargetAttr(obj, lvalue.name)

        assert False, 'Unsupported lvalue: %r' % lvalue

    def assign_to_target(self,
                         target: AssignmentTarget,
                         rvalue: Expression) -> Value:
        rvalue_reg = self.accept(rvalue)
        needs_box = rvalue_reg.type.is_unboxed and not target.type.is_unboxed
        if isinstance(target, AssignmentTargetRegister):
            if needs_box:
                rvalue_reg = self.box(rvalue_reg)
            return self.add(Assign(target.register, rvalue_reg))
        elif isinstance(target, AssignmentTargetAttr):
            if needs_box:
                rvalue_reg = self.box(rvalue_reg)
            return self.add(SetAttr(target.obj, target.attr, rvalue_reg, rvalue.line))
        elif isinstance(target, AssignmentTargetIndex):
            target_reg2 = self.translate_special_method_call(
                target.base,
                '__setitem__',
                [target.index, rvalue_reg],
                None,
                rvalue.line)
            if target_reg2 is not None:
                return target_reg2

            assert False, target.base.type

        assert False, 'Unsupported assignment target'

    def assign(self,
               lvalue: Lvalue,
               rvalue: Expression) -> AssignmentTarget:
        target = self.get_assignment_target(lvalue)
        self.assign_to_target(target, rvalue)
        return target

    def visit_if_stmt(self, stmt: IfStmt) -> Value:
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
        return INVALID_VALUE

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

    def visit_while_stmt(self, s: WhileStmt) -> Value:
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
        return INVALID_VALUE

    def visit_for_stmt(self, s: ForStmt) -> Value:
        if (isinstance(s.expr, CallExpr)
                and isinstance(s.expr.callee, RefExpr)
                and s.expr.callee.fullname == 'builtins.range'):
            self.push_loop_stack()

            # Special case for x in range(...)
            # TODO: Check argument counts and kinds; check the lvalue
            end = s.expr.args[0]
            end_reg = self.accept(end)

            # Initialize loop index to 0.
            assign_target = self.assign(s.index, IntExpr(0))
            assert isinstance(assign_target, AssignmentTargetRegister)
            index_reg = assign_target.register
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
            one_reg = self.add(LoadInt(1))
            self.add(Assign(index_reg, self.binary_op(index_reg, one_reg, '+', s.line)))

            # Go back to loop condition check.
            self.add(Goto(top.label))
            next = self.new_block()
            self.set_branches(branches, False, next)

            self.pop_loop_stack(end_block, next)
            return INVALID_VALUE

        if is_list_rprimitive(self.node_type(s.expr)):
            self.push_loop_stack()

            expr_reg = self.accept(s.expr)

            index_reg = self.alloc_temp(int_rprimitive)
            self.add(Assign(index_reg, self.add(LoadInt(0))))

            one_reg = self.add(LoadInt(1))

            assert isinstance(s.index, NameExpr)
            assert isinstance(s.index.node, Var)
            lvalue_reg = self.environment.add_local(s.index.node, self.node_type(s.index))

            condition_block = self.goto_new_block()

            # For compatibility with python semantics we recalculate the length
            # at every iteration.
            len_reg = self.add(PrimitiveOp([expr_reg], list_len_op, s.line))

            branch = Branch(index_reg, len_reg, INVALID_LABEL, INVALID_LABEL, Branch.INT_LT)
            self.add(branch)
            branches = [branch]

            body_block = self.new_block()
            self.set_branches(branches, True, body_block)

            target_list_type = self.types[s.expr]
            assert isinstance(target_list_type, Instance)
            target_type = self.type_to_rtype(target_list_type.args[0])
            value_box = self.add(PrimitiveOp([expr_reg, index_reg], list_get_item_op, s.line))

            self.add(Assign(lvalue_reg, self.unbox_or_cast(value_box, target_type, s.line)))

            s.body.accept(self)

            end_block = self.goto_new_block()
            self.add(Assign(index_reg, self.binary_op(index_reg, one_reg, '+', s.line)))
            self.add(Goto(condition_block.label))

            next_block = self.new_block()
            self.set_branches(branches, False, next_block)

            self.pop_loop_stack(end_block, next_block)

            return INVALID_VALUE

        assert False, 'for not supported'

    def visit_break_stmt(self, node: BreakStmt) -> Value:
        self.break_gotos[-1].append(Goto(INVALID_LABEL))
        self.add(self.break_gotos[-1][-1])
        return INVALID_VALUE

    def visit_continue_stmt(self, node: ContinueStmt) -> Value:
        self.continue_gotos[-1].append(Goto(INVALID_LABEL))
        self.add(self.continue_gotos[-1][-1])
        return INVALID_VALUE

    def visit_unary_expr(self, expr: UnaryExpr) -> Value:
        ereg = self.accept(expr.expr)
        for desc in unary_ops.get(expr.op, []):
            if is_subtype(ereg.type, desc.arg_types[0]):
                assert desc.result_type is not None
                target = self.add(PrimitiveOp([ereg], desc, expr.line))
                break
        else:
            # TODO: Fall back to generic C API
            assert False, 'Unsupported unary operation'

        return target

    def visit_op_expr(self, expr: OpExpr) -> Value:
        return self.binary_op(self.accept(expr.left), self.accept(expr.right), expr.op, expr.line)

    def binary_op(self,
                  lreg: Value,
                  rreg: Value,
                  expr_op: str,
                  line: int) -> Value:
        # Find the highest-priority primitive op that matches.
        matching = None  # type: Optional[OpDescription]
        for desc in binary_ops.get(expr_op, []):
            if (is_subtype(lreg.type, desc.arg_types[0])
                    and is_subtype(rreg.type, desc.arg_types[1])):
                if matching:
                    assert matching.priority != desc.priority, 'Ambiguous: %s, %s' % (matching,
                                                                                      desc)
                    if desc.priority > matching.priority:
                        matching = desc
                else:
                    matching = desc
        if matching:
            return self.primitive_op(matching, [lreg, rreg], line)

        # TODO: Fall back to generic operation
        assert False, 'Unsupported binary operation'

    def visit_index_expr(self, expr: IndexExpr) -> Value:
        base = self.accept(expr.base)

        if isinstance(base.type, RTuple):
            assert isinstance(expr.index, IntExpr)  # TODO
            return self.add(TupleGet(base, expr.index.value, expr.line))

        index_reg = self.accept(expr.index)
        target_reg = self.translate_special_method_call(
            base,
            '__getitem__',
            [index_reg],
            self.node_type(expr),
            expr.line)
        if target_reg is not None:
            return target_reg

        assert False, 'Unsupported indexing operation'

    def visit_int_expr(self, expr: IntExpr) -> Value:
        return self.add(LoadInt(expr.value))

    def is_native_name_expr(self, expr: NameExpr) -> bool:
        # TODO later we want to support cross-module native calls too
        assert expr.node, "RefExpr not resolved"
        if '.' in expr.node.fullname():
            module_name = '.'.join(expr.node.fullname().split('.')[:-1])
            return module_name == self.current_module_name

        return True

    def visit_name_expr(self, expr: NameExpr) -> Value:
        assert expr.node, "RefExpr not resolved"
        fullname = expr.node.fullname()
        if fullname in name_ref_ops:
            # Use special access op for this particular name.
            desc = name_ref_ops[fullname]
            assert desc.result_type is not None
            return self.add(PrimitiveOp([], desc, expr.line))

        if not self.is_native_name_expr(expr):
            return self.load_static_module_attr(expr)

        # TODO: We assume that this is a Var node, which is very limited
        assert isinstance(expr.node, Var)

        reg = self.environment.lookup(expr.node)
        return self.get_using_binder(reg, expr.node, expr)

    def get_using_binder(self, reg: Value, var: Var, expr: Expression) -> Value:
        assert var.type, "Variable missing type"
        var_type = self.type_to_rtype(var.type)
        target_type = self.node_type(expr)
        if var_type != target_type:
            # Cast/unbox to the narrower given by the binder.
            return self.unbox_or_cast(reg, target_type, expr.line)
        else:
            # Regular register access -- binder is not active.
            return reg

    def is_module_member_expr(self, expr: MemberExpr) -> bool:
        return isinstance(expr.expr, RefExpr) and expr.expr.kind == MODULE_REF

    def visit_member_expr(self, expr: MemberExpr) -> Value:
        if self.is_module_member_expr(expr):
            return self.load_static_module_attr(expr)

        else:
            obj = self.accept(expr.expr)
            return self.add(GetAttr(obj, expr.name, expr.line))

    def load_static_module_attr(self, expr: RefExpr) -> Value:
        assert expr.node, "RefExpr not resolved"
        module = '.'.join(expr.node.fullname().split('.')[:-1])
        right = expr.node.fullname().split('.')[-1]
        left = self.add(LoadStatic(object_rprimitive, c_module_name(module)))
        return self.add(PyGetAttr(self.node_type(expr), left, right, expr.line))

    def py_call(self, function: Value, args: List[Value],
                target_type: RType, line: int) -> Value:
        arg_boxes = [self.box(arg) for arg in args]  # type: List[Value]
        target_box = self.add(PyCall(function, arg_boxes, line))
        return self.unbox_or_cast(target_box, target_type, line)

    def py_method_call(self,
                       obj: Value,
                       method: Value,
                       args: List[Value],
                       target_type: RType,
                       line: int) -> Value:
        arg_boxes = [self.box(arg) for arg in args]  # type: List[Value]
        target_box = self.add(PyMethodCall(obj, method, arg_boxes))
        return self.unbox_or_cast(target_box, target_type, line)

    def coerce_native_call_args(self,
                                args: List[Value],
                                callee_type: Type,
                                line: int) -> List[Value]:
        assert isinstance(callee_type, CallableType)
        # TODO: Argument kinds
        formal_arg_types = [self.type_to_rtype(t) for t in callee_type.arg_types]
        coerced_arg_regs = []
        for reg, arg_type in zip(args, formal_arg_types):
            coerced_arg_regs.append(self.coerce(reg, arg_type, line))
        return coerced_arg_regs

    def visit_call_expr(self, expr: CallExpr) -> Value:
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
                arg_regs = self.coerce_native_call_args(
                    args, self.types[expr.callee], expr.line)
                return self.add(MethodCall(self.node_type(expr), obj, expr.callee.name,
                                           arg_regs, expr.line))
            else:
                method = self.load_static_unicode(expr.callee.name)
                return self.py_method_call(
                    obj, method, args, self.node_type(expr), expr.line)

        assert isinstance(expr.callee, NameExpr)  # TODO: Allow arbitrary callees

        # Gen the args
        fullname = expr.callee.fullname
        args = [self.accept(arg) for arg in expr.args]

        if fullname == 'builtins.len' and len(expr.args) == 1 and expr.arg_kinds == [ARG_POS]:
            expr_rtype = args[0].type
            if isinstance(expr_rtype, RTuple):
                # len() of fixed-length tuple can be trivially determined statically.
                return self.add(LoadInt(len(expr_rtype.types)))

        # Handle data-driven special-cased primitive call ops.
        target_type = self.node_type(expr)
        if fullname is not None:
            for desc in func_ops.get(fullname, []):
                if len(args) == len(desc.arg_types) and expr.arg_kinds == [ARG_POS] * len(args):
                    for actual_arg, formal_arg_type in zip(args, desc.arg_types):
                        if not is_subtype(actual_arg.type, formal_arg_type):
                            break
                    else:
                        assert desc.result_type is not None  # TODO: Support no return value
                        return self.primitive_op(desc, args, expr.line)

        fn = expr.callee.name  # TODO: fullname
        if not self.is_native_name_expr(expr.callee):
            # Python call
            function = self.accept(expr.callee)
            return self.py_call(function, args, target_type, expr.line)
        else:
            # Native call
            args = self.coerce_native_call_args(args, self.types[expr.callee], expr.line)
            return self.add(Call(target_type, fn, args, expr.line))

    def translate_cast_expr(self, expr: CastExpr) -> Value:
        src = self.accept(expr.expr)
        target_type = self.type_to_rtype(expr.type)
        return self.coerce(src, target_type, expr.line)

    def visit_conditional_expr(self, expr: ConditionalExpr) -> Value:
        branches = self.process_conditional(expr.cond)
        # Having actual Phi nodes would be really nice here!
        target = self.alloc_temp(self.node_type(expr))

        if_body = self.new_block()
        self.set_branches(branches, True, if_body)
        self.add(Assign(target, self.accept(expr.if_expr)))
        if_goto_next = Goto(INVALID_LABEL)
        self.add(if_goto_next)

        else_body = self.new_block()
        self.set_branches(branches, False, else_body)
        self.add(Assign(target, self.accept(expr.else_expr)))
        else_goto_next = Goto(INVALID_LABEL)
        self.add(else_goto_next)

        next = self.new_block()
        if_goto_next.label = next.label
        else_goto_next.label = next.label

        return target

    def translate_special_method_call(self,
                                      base_reg: Value,
                                      name: str,
                                      args: List[Value],
                                      result_type: Optional[RType],
                                      line: int) -> Optional[Value]:
        """Translate a method call which is handled nongenerically.

        These are special in the sense that we have code generated specifically for them.
        They tend to be method calls which have equivalents in C that are more direct
        than calling with the PyObject api.

        Return None if no translation found; otherwise return the target register.
        """
        base_type = base_reg.type
        fullname = '%s.%s' % (base_type.name, name)
        for desc in method_ops.get(fullname, []):
            if (is_subtype(base_type, desc.arg_types[0])
                    and len(args) == len(desc.arg_types) - 1
                    and all(is_subtype(arg.type, formal)
                            for arg, formal in zip(args, desc.arg_types[1:]))):
                # Found primitive call.
                coerced_args = []
                for arg, formal in zip(args, desc.arg_types[1:]):
                    reg = self.coerce(arg, formal, line)
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
                op_target = self.add(PrimitiveOp([base_reg] + coerced_args, desc, line))
                if coercion:
                    assert desc.result_type is not None
                    return self.coerce(op_target, result_type, line)
                else:
                    return op_target

        return None

    def visit_list_expr(self, expr: ListExpr) -> Value:
        items = [self.accept(item) for item in expr.items]
        return self.primitive_op(new_list_op, items, expr.line)

    def visit_tuple_expr(self, expr: TupleExpr) -> Value:
        tuple_type = self.node_type(expr)
        assert isinstance(tuple_type, RTuple)

        items = []
        for item_expr, item_type in zip(expr.items, tuple_type.types):
            reg = self.accept(item_expr)
            items.append(self.coerce(reg, item_type, item_expr.line))
        return self.add(TupleSet(items, expr.line))

    def visit_dict_expr(self, expr: DictExpr) -> Value:
        assert not expr.items  # TODO
        return self.add(PrimitiveOp([], new_dict_op, expr.line))

    # Conditional expressions

    int_relative_ops = {
        '==': Branch.INT_EQ,
        '!=': Branch.INT_NE,
        '<': Branch.INT_LT,
        '<=': Branch.INT_LE,
        '>': Branch.INT_GT,
        '>=': Branch.INT_GE,
    }

    def visit_str_expr(self, expr: StrExpr) -> Value:
        return self.load_static_unicode(expr.value)

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
            branch = Branch(reg, INVALID_VALUE, INVALID_LABEL, INVALID_LABEL, Branch.BOOL_EXPR)
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
            branch = Branch(left, INVALID_VALUE, INVALID_LABEL, INVALID_LABEL,
                            Branch.IS_NONE)
            if op == 'is not':
                branch.negated = True
        else:
            # General comparison -- evaluate both operands.
            left = self.accept(e.operands[0])
            right = self.accept(e.operands[1])
            if (op in ['==', '!=', '<', '<=', '>', '>=']
                    and is_same_type(left.type, int_rprimitive)
                    and is_same_type(right.type, int_rprimitive)):
                # Special op for int comparison.
                opcode = self.int_relative_ops[op]
                branch = Branch(left, right, INVALID_LABEL, INVALID_LABEL, opcode)
            else:
                # For other comparisons, generate a bool value and branch based on it. We need
                # this to handle exceptions in the comparison op.
                if op in ['in', 'not in']:
                    target = self.binary_op(left, right, 'in', e.line)
                else:
                    target = self.binary_op(left, right, op, e.line)
                target = self.coerce(target, bool_rprimitive, e.line)
                branch = Branch(target, INVALID_VALUE, INVALID_LABEL, INVALID_LABEL,
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

    def add(self, op: Op) -> Value:
        self.blocks[-1][-1].ops.append(op)
        if isinstance(op, RegisterOp):
            self.environment.add_op(op)
        return op

    def primitive_op(self, desc: OpDescription, args: List[Value], line: int) -> Value:
        assert desc.result_type is not None
        coerced = []
        for i, arg in enumerate(args):
            formal_type = self.op_arg_type(desc, i)
            arg = self.coerce(arg, formal_type, line)
            coerced.append(arg)
        return self.add(PrimitiveOp(coerced, desc, line))

    def op_arg_type(self, desc: OpDescription, n: int) -> RType:
        if n >= len(desc.arg_types):
            assert desc.is_var_arg
            return desc.arg_types[-1]
        return desc.arg_types[n]

    def accept(self, node: Node) -> Value:
        return node.accept(self)

    def alloc_temp(self, type: RType) -> Register:
        return self.environment.add_temp(type)

    def type_to_rtype(self, typ: Type) -> RType:
        return self.mapper.type_to_rtype(typ)

    def node_type(self, node: Expression) -> RType:
        if isinstance(node, IntExpr):
            # TODO: Don't special case IntExpr
            return int_rprimitive
        mypy_type = self.types[node]
        return self.type_to_rtype(mypy_type)

    def box(self, src: Value) -> Value:
        if src.type.is_unboxed:
            return self.add(Box(src))
        else:
            return src

    def unbox_or_cast(self, src: Value, target_type: RType, line: int) -> Value:
        if target_type.is_unboxed:
            return self.add(Unbox(src, target_type, line))
        else:
            return self.add(Cast(src, target_type, line))

    def box_expr(self, expr: Expression) -> Value:
        return self.box(self.accept(expr))

    def load_static_unicode(self, value: str) -> Value:
        """Loads a static unicode value into a register.

        This is useful for more than just unicode literals; for example, method calls
        also require a PyObject * form for the name of the method.
        """
        if value not in self.unicode_literals:
            self.unicode_literals[value] = '__unicode_' + str(len(self.unicode_literals))
        static_symbol = self.unicode_literals[value]
        return self.add(LoadStatic(str_rprimitive, static_symbol))

    def coerce(self, src: Value, target_type: RType, line: int) -> Value:
        """Generate a coercion/cast from one type to other (only if needed).

        For example, int -> object boxes the source int; int -> int emits nothing;
        object -> int unboxes the object. All conversions preserve object value.

        Returns the register with the converted value (may be same as src).
        """
        if src.type.is_unboxed and not target_type.is_unboxed:
            return self.box(src)
        if ((src.type.is_unboxed and target_type.is_unboxed)
                and not is_same_type(src.type, target_type)):
            # To go from one unboxed type to another, we go through a boxed
            # in-between value, for simplicity.
            tmp = self.box(src)
            return self.unbox_or_cast(tmp, target_type, line)
        if ((not src.type.is_unboxed and target_type.is_unboxed)
                or not is_subtype(src.type, target_type)):
            return self.unbox_or_cast(src, target_type, line)
        return src
