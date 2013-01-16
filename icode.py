"""icode: Register-based intermediate representation of mypy programs."""

from nodes import (
    FuncDef, IntExpr, MypyFile, NodeVisitor, ReturnStmt, NameExpr, WhileStmt,
    AssignmentStmt
)


class BasicBlock:
    """An icode basic block.

    Only the last instruction exits the block. Exceptions are not considered
    as exits.
    """
    void __init__(self):
        self.ops = <Opcode> []


class Opcode:
    """Abstract base class for all icode opcodes."""
    pass


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


class InvokeDirect(Opcode):
    """Invoke directly a global function (rN = g(rN, ...))."""
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

    str __str__(self):
        return 'return r%d' % self.retval


class Branch(Opcode):
    """Conditional branch (e.g. if r0 < r1 goto L2 else got L3)."""
    void __init__(self, int left, int right, str op, BasicBlock true,
                  BasicBlock false):
        self.left = left
        self.right = right
        self.op = op
        self.true = true
        self.false = false


class Goto(Opcode):
    """Unconditional jump (goto LN)."""
    void __init__(self, BasicBlock target):
        self.target = target


class BinOp(Opcode):
    """Primitive binary operation (e.g. r0 = r1 + r2 [int])."""
    void __init__(self, int target, int left, int right, str op):
        self.target = target
        self.left = left
        self.right = right
        self.op = op


class IcodeBuilder(NodeVisitor<int>):
    """Generate icode from a parse tree."""

    dict<str, BasicBlock> generated
    BasicBlock current
    int num_registers

    void __init__(self):
        self.generated = {}
        self.num_registers = 0

    int visit_mypy_file(self, MypyFile mfile):
        for d in mfile.defs:
            d.accept(self)
        return -1

    int visit_func_def(self, FuncDef fdef):
        initial = self.new_block()
        for s in fdef.body.body:
            s.accept(self)
        if not self.current.ops or not isinstance(self.current.ops[-1],
                                                  Return):
            r = self.alloc_register()
            self.add(SetRNone(r))
            self.add(Return(r))
        self.generated[fdef.name()] = initial
        return -1

    #
    # Statements
    #

    int visit_return_stmt(self, ReturnStmt s):
        retval = s.expr.accept(self)
        self.add(Return(retval))
        return -1

    int visit_assignment_stmt(self, AssignmentStmt s):
        # TODO
        pass

    int visit_while_stmt(self, WhileStmt s):
        # TODO
        pass

    #
    # Expressions
    #

    int visit_int_expr(self, IntExpr e):
        r = self.alloc_register()
        self.add(SetRI(r, e.value))
        return r

    int visit_name_expr(self, NameExpr e):
        # TODO
        pass

    #
    # Helpers
    #

    BasicBlock new_block(self):
        self.current = BasicBlock()
        return self.current

    void add(self, Opcode op):
        self.current.ops.append(op)

    int alloc_register(self):
        n = self.num_registers
        self.num_registers += 1
        return n


def render(block):
    return [str(op) for op in block.ops]
