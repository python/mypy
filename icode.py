"""icode: Register-based intermediate representation of mypy programs."""

from nodes import FuncDef, MypyFile, NodeVisitor


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


class IcodeBuilder(NodeVisitor<void>):
    """Generate icode from a parse tree."""

    dict<str, BasicBlock> generated

    void __init__(self):
        self.generated = {}

    void visit_mypy_file(self, MypyFile mfile):
        for d in mfile.defs:
            d.accept(self)

    void visit_func_def(self, FuncDef fdef):
        b = BasicBlock()
        b.ops.append(SetRNone(0))
        b.ops.append(Return(0))
        self.generated[fdef.name()] = b
        

def render(block):
    return [str(op) for op in block.ops]
