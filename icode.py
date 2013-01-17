"""icode: Register-based intermediate representation of mypy programs."""

from nodes import (
    FuncDef, IntExpr, MypyFile, NodeVisitor, ReturnStmt, NameExpr, WhileStmt,
    AssignmentStmt, Node, Var, OpExpr, Block, CallExpr, IfStmt, ParenExpr,
    UnaryExpr
)


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
    void __init__(self, int target, int source):
        self.target = target
        self.source = source


class SetRG(Opcode):
    """Assign global to register (rN = g)."""
    void __init__(self, int target, int source):
        self.target = target
        self.source = source


class CallDirect(Opcode):
    """Call directly a global function (rN = g(rN, ...))."""
    void __init__(self, int target, str func, int[] args):
        self.target = target
        self.func = func
        self.args = args

    str __str__(self):
        args = ', '.join(['r%d' % arg for arg in self.args])
        return 'r%d = %s(%s)' % (self.target, self.func, args)


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
    void __init__(self, int left, int right, str op, BasicBlock true_block,
                  BasicBlock false_block):
        self.left = left
        self.right = right
        self.op = op
        self.true_block = true_block
        self.false_block = false_block

    void invert(self):
        self.true_block, self.false_block = self.false_block, self.true_block
        self.op = self.inversion[self.op]

    str __str__(self):
        return 'if r%d %s r%d goto L%d else goto L%d' % (
            self.left, self.op, self.right,
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
        # This is tricky; not sure if this works *all* the time.
        self.negated = not self.negated
        self.true_block, self.false_block = self.false_block, self.true_block


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
    void __init__(self, int target, int left, int right, str op):
        self.target = target
        self.left = left
        self.right = right
        self.op = op

    str __str__(self):
        return 'r%d = r%d %s r%d [int]' % (self.target, self.left,
                                           self.op, self.right)


class UnaryOp(Opcode):
    """Primitive unary operation (e.g. r0 = -r1 [int])."""
    void __init__(self, int target, int operand, str op):
        self.target = target
        self.operand = operand
        self.op = op

    str __str__(self):
        return 'r%d = %sr%d [int]' % (self.target, self.op, self.operand)


class IcodeBuilder(NodeVisitor<int>):
    """Generate icode from a parse tree."""

    dict<str, BasicBlock[]> generated
    
    # List of generated blocks in the current scope
    BasicBlock[] blocks
    # Current basic block
    BasicBlock current
    # Number of registers allocated in the current scope
    int num_registers
    # Map local variable to allocated register
    dict<Node, int> lvar_regs

    void __init__(self):
        self.generated = {}
        self.num_registers = 0

    int visit_mypy_file(self, MypyFile mfile):
        for d in mfile.defs:
            d.accept(self)
        return -1

    int visit_func_def(self, FuncDef fdef):
        # TODO enter scope / leave scope
        self.lvar_regs = {}
        self.blocks = []
        self.new_block()
        for s in fdef.body.body:
            s.accept(self)
        if not self.current.ops or not isinstance(self.current.ops[-1],
                                                  Return):
            r = self.alloc_register()
            self.add(SetRNone(r))
            self.add(Return(r))
        self.generated[fdef.name()] = self.blocks
        return -1

    #
    # Statements
    #

    int visit_block(self, Block b):
        for stmt in b.body:
            stmt.accept(self)
        return -1

    int visit_return_stmt(self, ReturnStmt s):
        retval = s.expr.accept(self)
        self.add(Return(retval))
        return -1

    int visit_assignment_stmt(self, AssignmentStmt s):
        assert len(s.lvalues) == 1
        assert isinstance(s.lvalues[0], NameExpr)

        # TODO handle non-locals, attributes etc.

        rvalue = s.rvalue.accept(self)
        
        lval = (NameExpr)s.lvalues[0]
        if lval.is_def:
            reg = self.alloc_register()
            self.lvar_regs[lval.node] = reg
        else:
            reg = self.lvar_regs[lval.node]

        self.add(SetRR(reg, rvalue))

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
        r = self.alloc_register()
        self.add(SetRI(r, e.value))
        return r

    int visit_name_expr(self, NameExpr e):
        # TODO other names than locals
        return self.lvar_regs[e.node]

    int visit_op_expr(self, OpExpr e):
        # TODO arbitrary operand types
        left = e.left.accept(self)
        right = e.right.accept(self)
        target = self.alloc_register()
        self.add(BinOp(target, left, right, e.op))
        return target

    int visit_unary_expr(self, UnaryExpr e):
        operand = e.expr.accept(self)
        target = self.alloc_register()
        self.add(UnaryOp(target, operand, e.op))
        return target

    int visit_call_expr(self, CallExpr e):
        if isinstance(e.callee, NameExpr):
            callee = (NameExpr)e.callee
            target = self.alloc_register()
            self.add(CallDirect(target, callee.name, []))
            return target
        else:
            raise NotImplementedError()

    int visit_paren_expr(self, ParenExpr e):
        return e.expr.accept(self)

    #
    # Conditional expressions
    #

    Branch[] process_conditional(self, OpExpr e):
        # Return branches that need to be bound. The true and false parts
        # are always tweaked to be correctly.
        if e.op in ['==', '!=', '<', '<=', '>', '>=']:
            # TODO check that operand types are as expected
            left = e.left.accept(self)
            right = e.right.accept(self)
            branch = IfOp(left, right, e.op, None, None)
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
        value = e.accept(self)
        branch = IfR(value, None, None)
        self.add(branch)
        return [branch]

    #
    # Helpers
    #

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

    int alloc_register(self):
        n = self.num_registers
        self.num_registers += 1
        return n

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


def render(blocks):
    res = []
    for b in blocks:
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
