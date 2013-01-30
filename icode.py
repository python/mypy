"""icode: Register-based intermediate representation of mypy programs."""

from mtypes import Any, Instance, Type, Callable, FunctionLike
from nodes import (
    FuncDef, IntExpr, MypyFile, ReturnStmt, NameExpr, WhileStmt,
    AssignmentStmt, Node, Var, OpExpr, Block, CallExpr, IfStmt, ParenExpr,
    UnaryExpr, ExpressionStmt, CoerceExpr, TypeDef, MemberExpr, TypeInfo,
    VarDef
)
import nodes
from visitor import NodeVisitor
from subtypes import is_named_instance


# Operand kinds
REG_KIND = 0 # Register
INT_KIND = 1 # Integer literal


class FuncIcode:
    """Icode and related information for a function."""

    void __init__(self, int num_args, BasicBlock[] blocks,
                  int[] register_types):
        self.num_args = num_args
        self.blocks = blocks
        self.num_registers = len(register_types)
        self.register_types = register_types


class BasicBlock:
    """An icode basic block.

    Only the last instruction exits the block. Exceptions are not considered
    as exits.
    """
    void __init__(self, int label):
        self.ops = <Opcode> []
        self.label = label


class Opcode:
    """Abstract base class for all icode opcodes."""
    bool is_exit(self):
        """Does this opcode exit the block?"""
        return False


class SetRR(Opcode):
    """Assign register to register (rN = rN)."""
    void __init__(self, int target, int source):
        self.target = target
        self.source = source

    str __str__(self):
        return 'r%d = r%d' % (self.target, self.source)


class SetRI(Opcode):
    """Assign integer literal to register (rN = N)."""
    void __init__(self, int target, int intval):
        self.target = target
        self.intval = intval

    str __str__(self):
        return 'r%d = %d' % (self.target, self.intval)


class SetRNone(Opcode):
    """Assign None to register (rN = None)."""
    void __init__(self, int target):
        self.target = target

    str __str__(self):
        return 'r%d = None' % self.target


class SetGR(Opcode):
    """Assign register to global (g = rN)."""
    void __init__(self, str target, int source):
        self.target = target
        self.source = source

    str __str__(self):
        return '%s = r%d' % (self.target, self.source)


class SetRG(Opcode):
    """Assign global to register (rN = g)."""
    void __init__(self, int target, str source):
        self.target = target
        self.source = source

    str __str__(self):
        return 'r%d = %s' % (self.target, self.source)


class GetAttr(Opcode):
    """Look up an attribute directly (rN = rN.x [C])."""
    void __init__(self, int target, int object, str attr, TypeInfo type):
        self.target = target
        self.object = object
        self.attr = attr
        self.type = type

    str __str__(self):
        return 'r%d = r%d.%s [%s]' % (self.target, self.object, self.attr,
                                      self.type.name())


class SetAttr(Opcode):
    """Assign to an attribute directly (rN.x = rN [C])."""
    void __init__(self, int object, str attr, int source, TypeInfo type):
        self.object = object
        self.attr = attr
        self.source = source
        self.type = type

    str __str__(self):
        return 'r%d.%s = r%d [%s]' % (self.object, self.attr, self.source,
                                      self.type.name())


class CallDirect(Opcode):
    """Call directly a global function (rN = g(rN, ...))."""
    void __init__(self, int target, str func, int[] args):
        self.target = target
        self.func = func
        self.args = args

    str __str__(self):
        args = ', '.join(['r%d' % arg for arg in self.args])
        return 'r%d = %s(%s)' % (self.target, self.func, args)


class CallMethod(Opcode):
    """Call a method (rN = rN.m(rN, ...) [C])."""
    void __init__(self, int target, int object, str method, TypeInfo type,
                  int[] args):
        self.target = target
        self.object = object
        self.method = method
        self.type = type
        self.args = args

    str __str__(self):
        args = ', '.join(['r%d' % arg for arg in self.args])
        return 'r%d = r%d.%s(%s) [%s]' % (self.target, self.object,
                                          self.method, args, self.type.name())


class Construct(Opcode):
    """Construct an uninitialized class instance (rN = <construct C>)."""
    void __init__(self, int target, TypeInfo type):
        self.target = target
        self.type = type

    str __str__(self):
        return 'r%d = <construct %s>' % (self.target, self.type.name())


class Return(Opcode):
    """Return from function (return rN)."""
    void __init__(self, int retval):
        self.retval = retval
        
    bool is_exit(self):
        return True

    str __str__(self):
        return 'return r%d' % self.retval


class Branch(Opcode):
    """Abstract base class for branch opcode."""  
    BasicBlock true_block
    BasicBlock false_block
        
    bool is_exit(self):
        return True

    void invert(self):
        pass


class IfOp(Branch):
    inversion = {'==': '!=', '!=': '==',
                 '<': '>=', '<=': '>', '>': '<=', '>=': '<'}
    
    """Conditional operator branch (e.g. if r0 < r1 goto L2 else goto L3)."""
    void __init__(self,
                  int left, int left_kind,
                  int right, int right_kind,
                  str op, BasicBlock true_block,
                  BasicBlock false_block):
        self.left = left
        self.left_kind = left_kind
        self.right = right
        self.right_kind = right_kind
        self.op = op
        self.true_block = true_block
        self.false_block = false_block

    void invert(self):
        self.true_block, self.false_block = self.false_block, self.true_block
        self.op = self.inversion[self.op]

    str __str__(self):
        return 'if %s %s %s goto L%d else goto L%d' % (
            operand(self.left, self.left_kind), self.op,
            operand(self.right, self.right_kind),
            self.true_block.label, self.false_block.label)


class IfR(Branch):
    """Conditional value branch (if rN goto LN else goto LN). """
    bool negated
    
    void __init__(self, int value,
                  BasicBlock true_block, BasicBlock false_block):
        self.value = value
        self.true_block = true_block
        self.false_block = false_block
        self.negated = False

    void invert(self):
        # This is tricky; not sure if this works all the time.
        # This was implemented by trial and error and testing indicates that
        # it *seems* to work.
        self.negated = not self.negated
        self.true_block, self.false_block = self.false_block, self.true_block

    str __str__(self):
        prefix = ''
        if self.negated:
            prefix = 'not '
        return 'if %sr%d goto L%d else goto L%d' % (
            prefix, self.value, self.true_block.label, self.false_block.label)


class Goto(Opcode):
    """Unconditional jump (goto LN)."""
    void __init__(self, BasicBlock next_block):
        self.next_block = next_block
        
    bool is_exit(self):
        return True

    str __str__(self):
        return 'goto L%d' % self.next_block.label


class BinOp(Opcode):
    """Primitive binary operation (e.g. r0 = r1 + r2 [int])."""
    void __init__(self, int target,
                  int left, int left_kind,
                  int right, int right_kind,
                  str op):
        self.target = target
        self.left = left
        self.left_kind = left_kind
        self.right = right
        self.right_kind = right_kind
        self.op = op

    str __str__(self):
        return 'r%d = %s %s %s [int]' % (self.target,
                                         operand(self.left, self.left_kind),
                                         self.op,
                                         operand(self.right, self.right_kind))


class UnaryOp(Opcode):
    """Primitive unary operation (e.g. r0 = -r1 [int])."""
    void __init__(self, int target, int operand, str op):
        self.target = target
        self.operand = operand
        self.op = op

    str __str__(self):
        return 'r%d = %sr%d [int]' % (self.target, self.op, self.operand)


# Types of registers
INT = 0 # int, initialized to 0
REF = 1 # Arbitrary reference, initialized to None


class IcodeBuilder(NodeVisitor<int>):
    """Generate icode from a parse tree."""

    dict<str, FuncIcode> generated
    
    # List of generated blocks in the current scope
    BasicBlock[] blocks
    # Current basic block
    BasicBlock current
    # Number of registers allocated in the current scope
    int num_registers
    # Map local variable to allocated register
    dict<Node, int> lvar_regs
    # Stack of expression target registers (-1 => create new register)
    int[] targets
    # Storage type for each register (REG_* values)
    int[] register_types

    # Stack of inactive scopes
    tuple<BasicBlock[], int, dict<Node, int>>[] scopes

    void __init__(self, dict<Node, Type> types):
        self.generated = {}
        self.scopes = []
        self.targets = []
        self.types = types

    int visit_mypy_file(self, MypyFile mfile):
        self.enter()
        
        # Initialize non-int global variables.
        for name in sorted(mfile.names):
            node = mfile.names[name].node
            if isinstance(node, Var) and name != '__name__':
                v = (Var)node
                if not is_named_instance(v.type, 'builtins.int'):
                    tmp = self.alloc_register()
                    self.add(SetRNone(tmp))
                    self.add(SetGR(v.full_name(), tmp))
        
        for d in mfile.defs:
            d.accept(self)
        self.add_implicit_return()
        self.generated['__init'] = FuncIcode(0, self.blocks,
                                             self.register_types)
        # TODO leave?
        return -1

    int visit_func_def(self, FuncDef fdef):
        if fdef.name().endswith('*'):
            # Wrapper functions are not supported yet.
            return -1
        
        self.enter()

        for arg in fdef.args:
            self.add_local(arg)
        fdef.body.accept(self)
        self.add_implicit_return((Callable)fdef.type)

        if fdef.info:
            name = '%s.%s' % (fdef.info.name(), fdef.name())
        else:
            name = fdef.name()
        
        self.generated[name] = FuncIcode(len(fdef.args), self.blocks,
                                         self.register_types)

        self.leave()
        
        return -1

    void add_implicit_return(self, FunctionLike sig=None):
        if not self.current.ops or not isinstance(self.current.ops[-1],
                                                  Return):
            r = self.alloc_register()
            if sig and is_named_instance(((Callable)sig).ret_type,
                                         'builtins.int'):
                self.add(SetRI(r, 0))
            else:
                self.add(SetRNone(r))
            self.add(Return(r))

    int visit_type_def(self, TypeDef tdef):
        # TODO assignments in the body
        # TODO interfaces
        tdef.defs.accept(self)

        # Generate icode for the function that constructs an instance.
        self.make_class_constructor(tdef)
        
        return -1

    void make_class_constructor(self, TypeDef tdef):
        # Do we have a non-empty __init__?
        init = (FuncDef)tdef.info.get_method('__init__')
        init_argc = len(init.args) - 1
        if init.info.full_name() == 'builtins.object':
            init = None
        
        self.enter()
        if init:
            args = <int> []
            for arg in init.args[1:]:
                args.append(self.add_local(arg))
        target = self.alloc_register()
        self.add(Construct(target, tdef.info))
        # Inititalize data attributes to default values.
        for var in sorted(tdef.info.vars.keys()):
            temp = self.alloc_register()
            vtype = tdef.info.vars[var].type
            if is_named_instance(vtype, 'builtins.int'):
                self.add(SetRI(temp, 0))
            else:
                self.add(SetRNone(temp))
            self.add(SetAttr(target, var, temp, tdef.info))
        if init:
            self.add(CallMethod(self.alloc_register(), target, '__init__',
                                tdef.info, args))
        self.add(Return(target))
        self.generated[tdef.name] = FuncIcode(init_argc, self.blocks,
                                              self.register_types)
        self.leave()

    #
    # Statements
    #

    int visit_block(self, Block b):
        for stmt in b.body:
            stmt.accept(self)
        return -1

    int visit_var_def(self, VarDef d):
        assert len(d.items) == 1
        var = d.items[0][0]
        if d.kind == nodes.LDEF:
            reg = self.add_local(var)
            if d.init:
                self.accept(d.init, reg)
        elif d.kind == nodes.GDEF and d.init:
            init = self.accept(d.init)
            self.add(SetGR(var.full_name(), init))
        return -1

    int visit_expression_stmt(self, ExpressionStmt s):
        self.accept(s.expr)
        return -1

    int visit_return_stmt(self, ReturnStmt s):
        retval = self.accept(s.expr)
        self.add(Return(retval))
        return -1

    int visit_assignment_stmt(self, AssignmentStmt s):
        assert len(s.lvalues) == 1
        lvalue = s.lvalues[0]

        if isinstance(lvalue, NameExpr):
            name = (NameExpr)lvalue
            if name.kind == nodes.LDEF:
                if name.is_def:
                    reg = self.add_local((Var)name.node)
                else:
                    reg = self.lvar_regs[name.node]
                self.accept(s.rvalue, reg)
            elif name.kind == nodes.GDEF:
                assert isinstance(name.node, Var)
                var = (Var)name.node
                rvalue = self.accept(s.rvalue)
                self.add(SetGR(var.full_name(), rvalue))
            else:
                print(name, name.kind)
                raise NotImplementedError()
        elif isinstance(lvalue, MemberExpr):
            member = (MemberExpr)lvalue
            obj = self.accept(member.expr)
            obj_type = self.types[member.expr]
            assert isinstance(obj_type, Instance) # TODO more flexible
            typeinfo = ((Instance)obj_type).type
            source = self.accept(s.rvalue)
            if member.direct:
                self.add(SetAttr(obj, member.name, source, typeinfo))
            else:
                temp = self.alloc_register()
                # TODO do not hard code set$ prefix
                self.add(CallMethod(temp, obj, 'set$' + member.name, typeinfo,
                                    [source]))
        else:
            pass # TODO globals etc.

    int visit_while_stmt(self, WhileStmt s):
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

    int visit_if_stmt(self, IfStmt s):
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

    int visit_int_expr(self, IntExpr e):
        r = self.target_register()
        self.add(SetRI(r, e.value))
        return r

    int visit_name_expr(self, NameExpr e):
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
            var = (Var)e.node
            if var.full_name() == 'builtins.None':
                self.add(SetRNone(target)) # Special opcode for None
            else:
                self.add(SetRG(target, var.full_name()))
            return target
        else:
            raise NotImplementedError('unsupported kind %d' % e.kind)

    int visit_member_expr(self, MemberExpr e):
        obj = self.accept(e.expr)
        obj_type = self.types[e.expr]
        assert isinstance(obj_type, Instance) # TODO more flexible
        typeinfo = ((Instance)obj_type).type
        target = self.target_register()
        if e.direct:
            self.add(GetAttr(target, obj, e.name, typeinfo))
        else:
            # TODO do not hard code '$' + ...
            self.add(CallMethod(target, obj, '$' + e.name, typeinfo, []))
        return target

    int visit_op_expr(self, OpExpr e):
        # TODO arbitrary operand types
        left, left_kind = self.get_operand(e.left)
        right, right_kind = self.get_operand(e.right)
        target = self.target_register()
        self.add(BinOp(target, left, left_kind, right, right_kind, e.op))
        return target

    tuple<int, int> get_operand(self, Node n):
        if isinstance(n, IntExpr):
            return ((IntExpr)n).value, INT_KIND
        else:
            return self.accept(n), REG_KIND

    int visit_unary_expr(self, UnaryExpr e):
        operand = self.accept(e.expr)
        target = self.target_register()
        self.add(UnaryOp(target, operand, e.op))
        return target

    int visit_call_expr(self, CallExpr e):
        args = <int> []
        for arg in e.args:
            args.append(self.accept(arg))
        if isinstance(e.callee, NameExpr):
            name = (NameExpr)e.callee
            target = self.target_register()
            self.add(CallDirect(target, name.name, args))
        elif isinstance(e.callee, MemberExpr):
            member = (MemberExpr)e.callee
            receiver = self.accept(member.expr)
            target = self.target_register()
            receiver_type = self.types[member.expr]
            assert isinstance(receiver_type, Instance) # TODO more flexible
            typeinfo = ((Instance)receiver_type).type
            self.add(CallMethod(target, receiver, member.name, typeinfo, args))
        else:
            raise NotImplementedError('call target %s' % type(e.callee))
        return target

    int visit_paren_expr(self, ParenExpr e):
        return e.expr.accept(self)

    int visit_coerce_expr(self, CoerceExpr e):
        if (is_named_instance(e.source_type, 'builtins.int') and
            isinstance(e.target_type, Any)):
            # This is a no-op currently.
            # TODO perhaps should do boxing in some cases...
            return e.expr.accept(self)
        else:
            # Non-trivial coercions not supported yet.
            raise NotImplementedError()

    #
    # Conditional expressions
    #

    Branch[] process_conditional(self, OpExpr e):
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

    Branch[] process_conditional(self, UnaryExpr e):
        if e.op == 'not':
            branches = self.process_conditional(e.expr)
            for b in branches:
                b.invert()
            return branches
        else:
            raise NotImplementedError()

    Branch[] process_conditional(self, ParenExpr e):
        return self.process_conditional(e.expr)

    Branch[] process_conditional(self, Node e):
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

    void enter(self):
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

    void leave(self):
        """Leave a scope."""
        self.blocks, self.num_registers, self.lvar_regs = self.scopes.pop()
        self.current = self.blocks[-1]

    BasicBlock new_block(self):
        new = BasicBlock(len(self.blocks))
        self.blocks.append(new)
        if self.current:
            if self.current.ops and not self.current.ops[-1].is_exit():
                self.add(Goto(new))
        self.current = new
        return new

    void add(self, Opcode op):
        self.current.ops.append(op)

    int accept(self, Node n, int target=-1):
        self.targets.append(target)
        actual = n.accept(self)
        self.targets.pop()
        return actual

    int alloc_register(self, int type=REF):
        # Temps are always set before access, so type does not matter for them.
        n = self.num_registers
        self.num_registers += 1
        self.register_types.append(type)
        return n

    int target_register(self):
        if self.targets[-1] < 0:
            return self.alloc_register()
        else:
            return self.targets[-1]

    int add_local(self, Var node):
        type = REF
        if is_named_instance(node.type, 'builtins.int'):
            type = INT
        reg = self.alloc_register(type)
        self.lvar_regs[node] = reg
        return reg
    
    void set_branches(self, Branch[] branches, bool condition,
                      BasicBlock target):
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


str[] filter_out_trivial_gotos(str[] disasm):
    """Filter out gotos to the next opcode (they are no-ops)."""
    res = <str> []
    for i, s in enumerate(disasm):
        if s.startswith('    goto '):
            label = s.split()[1]
            if i + 1 < len(disasm) and disasm[i+1].startswith('%s:' % label):
                # Omit goto
                continue
        res.append(s)
    return res


str operand(int n, int kind):
    if kind == INT_KIND:
        return str(n)
    else:
        return 'r%d' % n
