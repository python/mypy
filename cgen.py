"""Generate C code from icode."""

import os
import sys

from build import build
from errors import CompileError
import icode
from icode import (
    BasicBlock, SetRI, SetRR, SetRNone, IfOp, BinOp, Goto, Return, Opcode,
    CallDirect, FuncIcode
)
import transform


INDENT = 4


class CGenerator:
    FuncIcode func
    
    void __init__(self):
        self.out = <str> []
        self.prolog = ['#include "mypy.h"\n']
        self.indent = 0
    
    void generate_function(self, str name, FuncIcode func):
        self.func = func
        header = 'MValue %s(MEnv *e)' % name
        self.prolog.append('%s;\n' % header)
        self.emit(header)
        self.emit('{')
        self.emit('MValue t;')
        self.emit('MValue *frame = e->frame;')
        self.emit('frame += %d;' % func.num_registers)
        self.emit('e->frame = frame;')

        for b in func.blocks:
            self.emit('%s:' % label(b.label))
            for op in b.ops:
                self.opcode(op)

        self.emit('}')

    int_conditionals = {
        '<': 'MShortLt'
    }

    void opcode(self, SetRI opcode):
        self.emit('%s = %d;' % (reg(opcode.target), 2 * opcode.intval))

    void opcode(self, SetRR opcode):
        self.emit('%s = %s;' % (reg(opcode.target), reg(opcode.source)))

    void opcode(self, SetRNone opcode):
        self.emit('%s = MNone;' % reg(opcode.target))

    void opcode(self, IfOp opcode):
        left = operand(opcode.left, opcode.left_kind)
        right = operand(opcode.right, opcode.right_kind)
        op = self.int_conditionals[opcode.op]
        self.emit('if (%s(%s, %s))' % (op, left, right))
        self.emit('    goto %s;' % (label(opcode.true_block.label)))
        self.emit('else')
        self.emit('    goto %s;' % (label(opcode.false_block.label)))

    void opcode(self, BinOp opcode):
        target = reg(opcode.target)
        left = operand(opcode.left, opcode.left_kind)
        right = operand(opcode.right, opcode.right_kind)
        self.emit('t = %s %s %s;' % (left, opcode.op, right))
        self.emit('if (MIsAddOverflow(t, %s, %s)) {' % (left, right))
        self.emit('t = MIntAdd(e, %s, %s);' % (left, right))
        self.emit('if (t == MError) {')
        self.emit_return('MError')
        self.emit('}')
        self.emit('}')
        self.emit('%s = t;' % target)

    void opcode(self, Goto opcode):
        self.emit('goto %s;' % label(opcode.next_block.label))

    void opcode(self, Return opcode):
        self.emit_return(reg(opcode.retval))

    void opcode(self, CallDirect opcode):
        self.emit('%s = M%s(e);' % (reg(opcode.target), opcode.func))
        # TODO check error

    void opcode(self, Opcode opcode):
        """Default case."""
        raise NotImplementedError(type(opcode))

    #
    # Helpers
    #

    void emit(self, str s):
        if '}' in s:
            self.indent -= INDENT
        indent = self.indent
        if s.endswith(':'):
            indent -= INDENT
        self.out.append(' ' * indent + s + '\n')
        if '{' in s:
            self.indent += INDENT

    void emit_return(self, str retval):
        if retval != 'MError':
            self.emit('t = %s;' % retval)
        self.emit('e->frame = frame - %d;' % self.func.num_registers)
        if retval != 'MError':
            self.emit('return t;')
        else:
            self.emit('return %s;' % retval)


str reg(int n):
    return 'frame[%d]' % n

str label(int n):
    return 'L%d' % n

str operand(int n, int kind):
    if kind == icode.INT_KIND:
        return str(n * 2)
    else:
        return reg(n)


if __name__ == '__main__':
    # Construct input as a single single.
    program = sys.argv[1]
    text = open(program).read()
    
    # Parse and type check the input program.
    try:
        trees, symtable, infos, types = build(program_text=text,
                                              program_file_name=program,
                                              use_test_builtins=False,
                                              do_type_check=True)
    except CompileError as e:
        for s in e.messages:
            sys.stderr.write(s + '\n')
        sys.exit(1)
        
    builder = icode.IcodeBuilder()
    # Transform each file separately.
    for t in trees:
        # Skip the builtins module and files with '_skip.' in the path.
        if not t.path.endswith('/builtins.py') and '_skip.' not in t.path:
            # Transform parse tree and produce pretty-printed output.
            transform = transform.DyncheckTransformVisitor(types, symtable,
                                                           True)
            t.accept(transform)
            t.accept(builder)

    cgen = CGenerator()
    for fn in builder.generated.keys():
        cgen.generate_function('M' + fn, builder.generated[fn])

    out = open('_out.c', 'w')
    
    for s in cgen.prolog:
        out.write(s)
    out.write('\n')
    for s in cgen.out:
        out.write(s)

    out.write(
'''
int main(int argc, char **argv) {
    MValue stack[1024];
    MEnv env;
    env.frame = stack;
    M__init(&env);
    return 0;
}
''')
    
    out.close()

    os.system('gcc -O2 _out.c runtime.c')
