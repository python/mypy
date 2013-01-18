"""Generate C code from icode."""

import os
import sys

from build import build
import icode
from icode import (
    BasicBlock, SetRI, SetRR, SetRNone, IfOp, BinOp, Goto, Return, Opcode,
    CallDirect
)
import transform


INDENT = 4


class CGenerator:
    void __init__(self):
        self.out = <str> []
        self.prolog = ['#include "mypy.h"\n']
        self.indent = 0
    
    void generate_function(self, str name, BasicBlock[] blocks):
        header = 'MValue %s(MEnv *e)' % name
        self.prolog.append('%s;\n' % header)
        self.emit(header)
        self.emit('{')

        for b in blocks:
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
        op = self.int_conditionals[opcode.op]
        self.emit('if (%s(%s, %s))' % (op, reg(opcode.left),
                                       reg(opcode.right)))
        self.emit('    goto %s;' % (label(opcode.true_block.label)))
        self.emit('else')
        self.emit('    goto %s;' % (label(opcode.false_block.label)))

    void opcode(self, BinOp opcode):
        self.emit('%s = %s %s %s;' % (reg(opcode.target), reg(opcode.left),
                                      opcode.op, reg(opcode.right)))
        self.emit('if (MIsAddOverflow(%s, %s, %s)) {' % (reg(opcode.target),
                                                         reg(opcode.left),
                                                         reg(opcode.right)))
        self.emit('%s = MIntAdd(e, %s, %s);' % (reg(opcode.target),
                                                    reg(opcode.left),
                                                    reg(opcode.right)))
        self.emit('if (%s == MError)' % reg(opcode.target))
        self.emit('    return MError;')
        self.emit('}')

    void opcode(self, Goto opcode):
        self.emit('goto %s;' % label(opcode.next_block.label))

    void opcode(self, Return opcode):
        self.emit('return %s;' % reg(opcode.retval))

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


str reg(int n):
    return 'e->frame[%d]' % n

str label(int n):
    return 'L%d' % n


if __name__ == '__main__':
    # Construct input as a single single.
    text = open('t.py').read()
    # Parse and type check the input program.
    trees, symtable, infos, types = build(program_text=text,
                                          program_file_name='t.py',
                                          use_test_builtins=False,
                                          do_type_check=True)
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
    for fn in ['__init', 'f']:
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
