"""icode: Register-based intermediate representation of mypy programs."""

from typing import List, Undefined, Dict, Tuple, cast, overload

from mypy.types import AnyType, Instance, Type, Callable, FunctionLike
from mypy.nodes import (
    FuncDef, IntExpr, MypyFile, ReturnStmt, NameExpr, WhileStmt,
    AssignmentStmt, Node, Var, OpExpr, Block, CallExpr, IfStmt, ParenExpr,
    UnaryExpr, ExpressionStmt, CoerceExpr, ClassDef, MemberExpr, TypeInfo,
    VarDef, SuperExpr, IndexExpr, UndefinedExpr
)
from mypy import nodes
from mypy.visitor import NodeVisitor
from mypy.subtypes import is_named_instance


# Operand kinds
REG_KIND = 0 # Register
INT_KIND = 1 # Integer literal


class FuncIcode:
    """Icode and related information for a function."""

    def __init__(self, num_args: int, blocks: 'List[BasicBlock]',
                  register_types: List[int]) -> None:
        self.num_args = num_args
        self.blocks = blocks
        self.num_registers = len(register_types)
        self.register_types = register_types


class BasicBlock:
    """An icode basic block.

    Only the last instruction exits the block. Exceptions are not considered
    as exits.
    """
    def __init__(self, label: int) -> None:
        self.ops = List[Opcode]()
        self.label = label


class Opcode:
    """Abstract base class for all icode opcodes."""
    def is_exit(self) -> bool:
        """Does this opcode exit the block?"""
        return False


class SetRR(Opcode):
    """Assign register to register (rN = rN)."""
    def __init__(self, target: int, source: int) -> None:
        self.target = target
        self.source = source

    def __str__(self) -> str:
        return 'r%d = r%d' % (self.target, self.source)


class SetRI(Opcode):
    """Assign integer literal to register (rN = N)."""
    def __init__(self, target: int, intval: int) -> None:
        self.target = target
        self.intval = intval

    def __str__(self) -> str:
        return 'r%d = %d' % (self.target, self.intval)


class SetRNone(Opcode):
    """Assign None to register (rN = None)."""
    def __init__(self, target: int) -> None:
        self.target = target

    def __str__(self) -> str:
        return 'r%d = None' % self.target


class SetGR(Opcode):
    """Assign register to global (g = rN)."""
    def __init__(self, target: str, source: int) -> None:
        self.target = target
        self.source = source

    def __str__(self) -> str:
        return '%s = r%d' % (self.target, self.source)


class SetRG(Opcode):
    """Assign global to register (rN = g)."""
    def __init__(self, target: int, source: str) -> None:
        self.target = target
        self.source = source

    def __str__(self) -> str:
        return 'r%d = %s' % (self.target, self.source)


class GetAttr(Opcode):
    """Look up an attribute directly (rN = rN.x [C])."""
    def __init__(self, target: int, object: int, attr: str,
                 type: TypeInfo) -> None:
        self.target = target
        self.object = object
        self.attr = attr
        self.type = type

    def __str__(self) -> str:
        return 'r%d = r%d.%s [%s]' % (self.target, self.object, self.attr,
                                      self.type.name())


class SetAttr(Opcode):
    """Assign to an attribute directly (rN.x = rN [C])."""
    def __init__(self, object: int, attr: str, source: int,
                 type: TypeInfo) -> None:
        self.object = object
        self.attr = attr
        self.source = source
        self.type = type

    def __str__(self) -> str:
        return 'r%d.%s = r%d [%s]' % (self.object, self.attr, self.source,
                                      self.type.name())


class CallDirect(Opcode):
    """Call directly a global function (rN = g(rN, ...))."""
    def __init__(self, target: int, func: str, args: List[int]) -> None:
        self.target = target
        self.func = func
        self.args = args

    def __str__(self) -> str:
        args = ', '.join(['r%d' % arg for arg in self.args])
        return 'r%d = %s(%s)' % (self.target, self.func, args)


class CallMethod(Opcode):
    """Call a method (rN = rN.m(rN, ...) [C]).

    Attributes:
      target: lvalue for the result (register)
      object: receiver (register)
      method: method name
      type: vtable to use
      args: arguments (registers)
      static: resolve method statically (be default, at runtime)
    """
    def __init__(self, target: int, object: int, method: str, type: TypeInfo,
                 args: List[int], static: bool = False) -> None:
        self.target = target
        self.object = object
        self.method = method
        self.type = type
        self.args = args
        self.static = static

    def __str__(self) -> str:
        args = ', '.join(['r%d' % arg for arg in self.args])
        cls = self.type.name()
        if self.static:
            cls = 'static ' + cls
        return 'r%d = r%d.%s(%s) [%s]' % (self.target, self.object,
                                          self.method, args, cls)


class Construct(Opcode):
    """Construct an uninitialized class instance (rN = <construct C>)."""
    def __init__(self, target: int, type: TypeInfo) -> None:
        self.target = target
        self.type = type

    def __str__(self) -> str:
        return 'r%d = <construct %s>' % (self.target, self.type.name())


class Return(Opcode):
    """Return from function (return rN)."""
    def __init__(self, retval: int) -> None:
        self.retval = retval
        
    def is_exit(self) -> bool:
        return True

    def __str__(self) -> str:
        return 'return r%d' % self.retval


class Branch(Opcode):
    """Abstract base class for branch opcode."""  
    true_block = Undefined # type: BasicBlock
    false_block = Undefined # type: BasicBlock
        
    def is_exit(self) -> bool:
        return True

    def invert(self) -> None:
        pass


class IfOp(Branch):
    inversion = {'==': '!=', '!=': '==',
                 '<': '>=', '<=': '>', '>': '<=', '>=': '<'}
    
    """Conditional operator branch (e.g. if r0 < r1 goto L2 else goto L3)."""
    def __init__(self,
                 left: int, left_kind: int,
                 right: int, right_kind: int,
                 op: str, true_block: BasicBlock,
                 false_block: BasicBlock) -> None:
        self.left = left
        self.left_kind = left_kind
        self.right = right
        self.right_kind = right_kind
        self.op = op
        self.true_block = true_block
        self.false_block = false_block

    def invert(self) -> None:
        self.true_block, self.false_block = self.false_block, self.true_block
        self.op = self.inversion[self.op]

    def __str__(self) -> str:
        return 'if %s %s %s goto L%d else goto L%d' % (
            operand(self.left, self.left_kind), self.op,
            operand(self.right, self.right_kind),
            self.true_block.label, self.false_block.label)


class IfR(Branch):
    """Conditional value branch (if rN goto LN else goto LN). """
    negated = False
    
    def __init__(self, value: int,
                 true_block: BasicBlock, false_block: BasicBlock) -> None:
        self.value = value
        self.true_block = true_block
        self.false_block = false_block
        self.negated = False

    def invert(self) -> None:
        # This is tricky; not sure if this works all the time.
        # This was implemented by trial and error and testing indicates that
        # it *seems* to work.
        self.negated = not self.negated
        self.true_block, self.false_block = self.false_block, self.true_block

    def __str__(self) -> str:
        prefix = ''
        if self.negated:
            prefix = 'not '
        return 'if %sr%d goto L%d else goto L%d' % (
            prefix, self.value, self.true_block.label, self.false_block.label)


class Goto(Opcode):
    """Unconditional jump (goto LN)."""
    def __init__(self, next_block: BasicBlock) -> None:
        self.next_block = next_block
        
    def is_exit(self) -> bool:
        return True

    def __str__(self) -> str:
        return 'goto L%d' % self.next_block.label


class BinOp(Opcode):
    """Primitive binary operation (e.g. r0 = r1 + r2 [int])."""
    def __init__(self, target: int,
                 left: int, left_kind: int,
                 right: int, right_kind: int,
                 op: str) -> None:
        self.target = target
        self.left = left
        self.left_kind = left_kind
        self.right = right
        self.right_kind = right_kind
        self.op = op

    def __str__(self) -> str:
        return 'r%d = %s %s %s [int]' % (self.target,
                                         operand(self.left, self.left_kind),
                                         self.op,
                                         operand(self.right, self.right_kind))


class UnaryOp(Opcode):
    """Primitive unary operation (e.g. r0 = -r1 [int])."""
    def __init__(self, target: int, operand: int, op: str) -> None:
        self.target = target
        self.operand = operand
        self.op = op

    def __str__(self) -> str:
        return 'r%d = %sr%d [int]' % (self.target, self.op, self.operand)


# Types of registers
INT = 0 # int, initialized to 0
REF = 1 # Arbitrary reference, initialized to None


class IcodeBuilder(NodeVisitor[int]):
    """Generate icode from a parse tree."""

    generated = Undefined(Dict[str, FuncIcode])
    
    # List of generated blocks in the current scope
    blocks = Undefined(List[BasicBlock])
    # Current basic block
    current = Undefined(BasicBlock)
    # Number of registers allocated in the current scope
    num_registers = 0
    # Map local variable to allocated register
    lvar_regs = Undefined(Dict[Node, int])
    # Stack of expression target registers (-1 => create new register)
    targets = Undefined(List[int])
    # Storage type for each register (REG_* values)
    register_types = Undefined(List[int])

    # Stack of inactive scopes
    scopes = Undefined(List[Tuple[List[BasicBlock], int, Dict[Node, int]]])

    def __init__(self, types: Dict[Node, Type]) -> None:
        self.generated = {}
        self.scopes = []
        self.targets = []
        self.types = types

    def visit_mypy_file(self, mfile: MypyFile) -> int:
        if mfile.fullname() in ('typing', 'abc'):
            # These module are special; their contents are currently all
            # built-in primitives.
            return -1
        
        self.enter()
        
        # Initialize non-int global variables.
        for name in sorted(mfile.names):
            node = mfile.names[name].node
            if (isinstance(node, Var) and
                    name not in nodes.implicit_module_attrs):
                v = cast(Var, node)
                if (not is_named_instance(v.type, 'builtins.int')
                        and v.fullname() != 'typing.Undefined'):
                    tmp = self.alloc_register()
                    self.add(SetRNone(tmp))
                    self.add(SetGR(v.fullname(), tmp))
        
        for d in mfile.defs:
            d.accept(self)
        self.add_implicit_return()
        self.generated['__init'] = FuncIcode(0, self.blocks,
                                             self.register_types)
        # TODO leave?
        return -1

    def visit_func_def(self, fdef: FuncDef) -> int:
        if fdef.name().endswith('*'):
            # Wrapper functions are not supported yet.
            return -1
        
        self.enter()

        for arg in fdef.args:
            self.add_local(arg)
        fdef.body.accept(self)
        self.add_implicit_return(cast(Callable, fdef.type))

        if fdef.info:
            name = '%s.%s' % (fdef.info.name(), fdef.name())
        else:
            name = fdef.name()
        
        self.generated[name] = FuncIcode(len(fdef.args), self.blocks,
                                         self.register_types)

        self.leave()
        
        return -1

    def add_implicit_return(self, sig: FunctionLike = None) -> None:
        if not self.current.ops or not isinstance(self.current.ops[-1],
                                                  Return):
            r = self.alloc_register()
            if sig and is_named_instance((cast(Callable, sig)).ret_type,
                                         'builtins.int'):
                self.add(SetRI(r, 0))
            else:
                self.add(SetRNone(r))
            self.add(Return(r))

    def visit_class_def(self, tdef: ClassDef) -> int:
        # TODO assignments in the body
        # TODO multiple inheritance
        tdef.defs.accept(self)

        # Generate icode for the function that constructs an instance.
        self.make_class_constructor(tdef)
        
        return -1

    def make_class_constructor(self, tdef: ClassDef) -> None:
        # Do we have a non-empty __init__?
        init = cast(FuncDef, tdef.info.get_method('__init__'))
        init_argc = len(init.args) - 1
        if init.info.fullname() == 'builtins.object':
            init = None
        
        self.enter()
        if init:
            args = [] # type: List[int]
            for arg in init.args[1:]:
                args.append(self.add_local(arg))
        target = self.alloc_register()
        self.add(Construct(target, tdef.info))
        # Inititalize data attributes to default values.
        for name, node in sorted(tdef.info.names.items()):
            if isinstance(node.node, Var):
                var = cast(Var, node.node)
                temp = self.alloc_register()
                vtype = var.type
                if is_named_instance(vtype, 'builtins.int'):
                    self.add(SetRI(temp, 0))
                else:
                    self.add(SetRNone(temp))
                self.add(SetAttr(target, name, temp, tdef.info))
        if init:
            self.add(CallMethod(self.alloc_register(), target, '__init__',
                                init.info, args, static=True))
        self.add(Return(target))
        self.generated[tdef.name] = FuncIcode(init_argc, self.blocks,
                                              self.register_types)
        self.leave()

    #
    # Statements
    #

    def visit_block(self, b: Block) -> int:
        for stmt in b.body:
            stmt.accept(self)
        return -1

    def visit_var_def(self, d: VarDef) -> int:
        assert len(d.items) == 1
        var = d.items[0]
        if d.kind == nodes.LDEF:
            reg = self.add_local(var)
            if d.init:
                self.accept(d.init, reg)
        elif d.kind == nodes.GDEF and d.init:
            init = self.accept(d.init)
            self.add(SetGR(var.fullname(), init))
        return -1

    def visit_expression_stmt(self, s: ExpressionStmt) -> int:
        self.accept(s.expr)
        return -1

    def visit_return_stmt(self, s: ReturnStmt) -> int:
        retval = self.accept(s.expr)
        self.add(Return(retval))
        return -1

    def visit_assignment_stmt(self, s: AssignmentStmt) -> int:
        assert len(s.lvalues) == 1
        lvalue = s.lvalues[0]

        undefined_rvalue = is_undefined_initializer(s.rvalue)

        if isinstance(lvalue, NameExpr):
            name = cast(NameExpr, lvalue)
            if name.kind == nodes.LDEF:
                if name.is_def or s.type:
                    reg = self.add_local(cast(Var, name.node))
                else:
                    reg = self.lvar_regs[name.node]
                if not undefined_rvalue:
                    self.accept(s.rvalue, reg)
            elif name.kind == nodes.GDEF:
                assert isinstance(name.node, Var)
                if not undefined_rvalue:
                    var = cast(Var, name.node)
                    rvalue = self.accept(s.rvalue)
                    self.add(SetGR(var.fullname(), rvalue))
            elif name.kind == nodes.MDEF and undefined_rvalue:
                # Attribute initializers not supported yet.
                pass
            else:
                raise NotImplementedError()
        elif isinstance(lvalue, MemberExpr):
            member = cast(MemberExpr, lvalue)
            obj = self.accept(member.expr)
            obj_type = self.types[member.expr]
            assert isinstance(obj_type, Instance) # TODO more flexible
            typeinfo = (cast(Instance, obj_type)).type
            source = self.accept(s.rvalue)
            if member.direct:
                self.add(SetAttr(obj, member.name, source, typeinfo))
            else:
                temp = self.alloc_register()
                # TODO do not hard code set$ prefix
                self.add(CallMethod(temp, obj, 'set$' + member.name, typeinfo,
                                    [source]))
        elif isinstance(lvalue, IndexExpr):
            indexexpr = cast(IndexExpr, lvalue)
            obj_type = self.types[indexexpr.base]
            assert isinstance(obj_type, Instance) # TODO more flexible
            typeinfo = (cast(Instance, obj_type)).type
            base = self.accept(indexexpr.base)
            index = self.accept(indexexpr.index)
            value = self.accept(s.rvalue)
            temp = self.alloc_register()
            self.add(CallMethod(temp, base, '__setitem__', typeinfo,
                                [index, value]))
        else:
            raise RuntimeError()

    def visit_while_stmt(self, s: WhileStmt) -> int:
        # Split block so that we get a handle to the top of the loop.
        top = self.new_block()
        branches = self.process_conditional(s.expr)
        body = self.new_block()
        # Bind "true" branches to the body block.
        self.set_branches(branches, True, body)
        s.body.accept(self)
        # Add branch to the top at the end of the body.
        self.add(Goto(top))
        next = self.new_block()
        # Bind "false" branches to the new block.
        self.set_branches(branches, False, next)
        return -1

    def visit_if_stmt(self, s: IfStmt) -> int:
        # If condition + body.
        branches = self.process_conditional(s.expr[0])
        if_body = self.new_block()
        self.set_branches(branches, True, if_body)
        s.body[0].accept(self)
        if s.else_body:
            # Else block.
            goto = Goto(None)
            self.add(goto)
            else_body = self.new_block()
            self.set_branches(branches, False, else_body)
            s.else_body.accept(self)
            next = self.new_block()
            goto.next_block = next
        else:
            # No else block.
            next = self.new_block()
            self.set_branches(branches, False, next)
        return -1

    #
    # Expressions (values)
    #

    def visit_int_expr(self, e: IntExpr) -> int:
        r = self.target_register()
        self.add(SetRI(r, e.value))
        return r

    def visit_name_expr(self, e: NameExpr) -> int:
        # TODO other names than locals
        if e.kind == nodes.LDEF:
            target = self.targets[-1]
            source = self.lvar_regs[e.node]
            if target < 0:
                return source
            else:
                self.add(SetRR(target, source))
                return target
        elif e.kind == nodes.GDEF:
            target = self.target_register()
            assert isinstance(e.node, Var) # TODO more flexible
            var = cast(Var, e.node)
            if var.fullname() == 'builtins.None':
                self.add(SetRNone(target)) # Special opcode for None
            else:
                self.add(SetRG(target, var.fullname()))
            return target
        else:
            raise NotImplementedError('unsupported kind %d' % e.kind)

    def visit_member_expr(self, e: MemberExpr) -> int:
        obj = self.accept(e.expr)
        obj_type = self.types[e.expr]
        assert isinstance(obj_type, Instance) # TODO more flexible
        typeinfo = (cast(Instance, obj_type)).type
        target = self.target_register()
        if e.direct:
            self.add(GetAttr(target, obj, e.name, typeinfo))
        else:
            # TODO do not hard code '$' + ...
            self.add(CallMethod(target, obj, '$' + e.name, typeinfo, []))
        return target

    def visit_op_expr(self, e: OpExpr) -> int:
        # TODO arbitrary operand types
        left_type = self.types[e.left]
        right_type = self.types[e.right]
        if (is_named_instance(left_type, 'builtins.int') and
                is_named_instance(right_type, 'builtins.int')):
            # Primitive operation
            left, left_kind = self.get_operand(e.left)
            right, right_kind = self.get_operand(e.right)
            target = self.target_register()
            self.add(BinOp(target, left, left_kind, right, right_kind, e.op))
        else:
            # Generate method call
            inst = cast(Instance, left_type)
            left = self.accept(e.left)
            right = self.accept(e.right)
            target = self.target_register()
            method = nodes.op_methods[e.op]
            if e.op == 'in':
                left, right = right, left
                inst = cast(Instance, right_type)
            self.add(CallMethod(target, left, method, inst.type, [right]))
        return target

    def get_operand(self, n: Node) -> Tuple[int, int]:
        if isinstance(n, IntExpr):
            return (cast(IntExpr, n)).value, INT_KIND
        else:
            return self.accept(n), REG_KIND

    def visit_unary_expr(self, e: UnaryExpr) -> int:
        operand_type = self.types[e.expr]
        operand = self.accept(e.expr)
        target = self.target_register()
        if is_named_instance(operand_type, 'builtins.int'):
            self.add(UnaryOp(target, operand, e.op))
        else:
            if e.op == '-':
                method = '__neg__'
            elif e.op == '+':
                method = '__pos__'
            elif e.op == '~':
                method = '__invert__'
            else:
                raise NotImplementedError("unhandled op: " + e.op)
            inst = cast(Instance, operand_type) # TODO more flexible
            self.add(CallMethod(target, operand, method, inst.type, []))
        return target

    def visit_call_expr(self, e: CallExpr) -> int:
        args = [] # type: List[int]
        for arg in e.args:
            args.append(self.accept(arg))
        if isinstance(e.callee, NameExpr):
            name = cast(NameExpr, e.callee)
            target = self.target_register()
            self.add(CallDirect(target, name.name, args))
        elif isinstance(e.callee, MemberExpr):
            member = cast(MemberExpr, e.callee)
            receiver = self.accept(member.expr)
            target = self.target_register()
            receiver_type = self.types[member.expr]
            assert isinstance(receiver_type, Instance) # TODO more flexible
            typeinfo = (cast(Instance, receiver_type)).type
            self.add(CallMethod(target, receiver, member.name, typeinfo, args))
        elif isinstance(e.callee, SuperExpr):
            superexpr = cast(SuperExpr, e.callee)
            target = self.target_register()
            self.add(CallMethod(target, 0,
                                superexpr.name,
                                superexpr.info.bases[0].type,
                                args, static=True))
        else:
            raise NotImplementedError('call target %s' % type(e.callee))
        return target

    def visit_paren_expr(self, e: ParenExpr) -> int:
        return e.expr.accept(self)

    def visit_coerce_expr(self, e: CoerceExpr) -> int:
        if (is_named_instance(e.source_type, 'builtins.int') and
            isinstance(e.target_type, AnyType)):
            # This is a no-op currently.
            # TODO perhaps should do boxing in some cases...
            return e.expr.accept(self)
        else:
            # Non-trivial coercions not supported yet.
            raise NotImplementedError()

    def visit_index_expr(self, e: IndexExpr) -> int:
        # Generate method call
        basetype = cast(Instance, self.types[e.base])
        base = self.accept(e.base)
        index = self.accept(e.index)
        target = self.target_register()
        self.add(CallMethod(target, base, '__getitem__', basetype.type,
                            [index]))
        return target

    #
    # Conditional expressions
    #

    @overload
    def process_conditional(self, e: OpExpr) -> List[Branch]:
        # Return branches that need to be bound. The true and false parts
        # are always tweaked to be correctly.
        if e.op in ['==', '!=', '<', '<=', '>', '>=']:
            # TODO check that operand types are as expected
            left, left_kind = self.get_operand(e.left)
            right, right_kind = self.get_operand(e.right)
            branch = IfOp(left, left_kind, right, right_kind, e.op, None, None)
            self.add(branch)
            return [branch]
        elif e.op == 'and':
            # Short circuit 'and'.
            # TODO non-bool operands
            lbranches = self.process_conditional(e.left)
            new = self.new_block()
            self.set_branches(lbranches, True, new)
            rbraches = self.process_conditional(e.right)
            return lbranches + rbraches
        elif e.op == 'or':
            # Short circuit 'or'.
            # TODO non-bool operands
            lbranches = self.process_conditional(e.left)
            new = self.new_block()
            self.set_branches(lbranches, False, new)
            rbraches = self.process_conditional(e.right)
            return lbranches + rbraches
        else:
            raise NotImplementedError()

    @overload
    def process_conditional(self, e: UnaryExpr) -> List[Branch]:
        if e.op == 'not':
            branches = self.process_conditional(e.expr)
            for b in branches:
                b.invert()
            return branches
        else:
            raise NotImplementedError()

    @overload
    def process_conditional(self, e: ParenExpr) -> List[Branch]:
        return self.process_conditional(e.expr)

    @overload
    def process_conditional(self, e: Node) -> List[Branch]:
        """Catch-all variant for value expressions.

        Generate opcode of form 'if rN goto ...'.
        """
        value = self.accept(e)
        branch = IfR(value, None, None)
        self.add(branch)
        return [branch]

    #
    # Helpers
    #

    def enter(self) -> None:
        """Enter a new scope.

        Each function and the file top level is a separate scope.
        """
        self.scopes.append((self.blocks, self.num_registers, self.lvar_regs))
        self.blocks = []
        self.num_registers = 0
        self.register_types= []
        self.lvar_regs = {}
        self.current = None
        self.new_block()

    def leave(self) -> None:
        """Leave a scope."""
        self.blocks, self.num_registers, self.lvar_regs = self.scopes.pop()
        self.current = self.blocks[-1]

    def new_block(self) -> BasicBlock:
        new = BasicBlock(len(self.blocks))
        self.blocks.append(new)
        if self.current:
            if self.current.ops and not self.current.ops[-1].is_exit():
                self.add(Goto(new))
        self.current = new
        return new

    def add(self, op: Opcode) -> None:
        self.current.ops.append(op)

    def accept(self, n: Node, target: int = -1) -> int:
        self.targets.append(target)
        actual = n.accept(self)
        self.targets.pop()
        return actual

    def alloc_register(self, type: int = REF) -> int:
        # Temps are always set before access, so type does not matter for them.
        n = self.num_registers
        self.num_registers += 1
        self.register_types.append(type)
        return n

    def target_register(self) -> int:
        if self.targets[-1] < 0:
            return self.alloc_register()
        else:
            return self.targets[-1]

    def add_local(self, node: Var) -> int:
        type = REF
        if is_named_instance(node.type, 'builtins.int'):
            type = INT
        reg = self.alloc_register(type)
        self.lvar_regs[node] = reg
        return reg
    
    def set_branches(self, branches: List[Branch], condition: bool,
                     target: BasicBlock) -> None:
        """Set branch targets for the given condition (True or False).

        If the target has already been set for a branch, skip the branch.
        """
        for b in branches:
            if condition:
                if not b.true_block:
                    b.true_block = target
            else:
                if not b.false_block:
                    b.false_block = target


def render(func):
    res = []
    for b in func.blocks:
        if res:
            res.append('L%d:' % b.label)
        res.extend(['    ' + str(op) for op in b.ops])

    return filter_out_trivial_gotos(res)


def filter_out_trivial_gotos(disasm: List[str]) -> List[str]:
    """Filter out gotos to the next opcode (they are no-ops)."""
    res = [] # type: List[str]
    for i, s in enumerate(disasm):
        if s.startswith('    goto '):
            label = s.split()[1]
            if i + 1 < len(disasm) and disasm[i+1].startswith('%s:' % label):
                # Omit goto
                continue
        res.append(s)
    return res


def operand(n: int, kind: int) -> str:
    if kind == INT_KIND:
        return str(n)
    else:
        return 'r%d' % n


def is_undefined_initializer(node: Node) -> bool:
    return ((isinstance(node, CallExpr) and
             isinstance((cast(CallExpr, node)).analyzed, UndefinedExpr)) or
            (isinstance(node, NameExpr)
             and (cast(NameExpr, node)).fullname == 'typing.Undefined'))
