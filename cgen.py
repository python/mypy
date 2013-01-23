"""Generate C code from icode."""

import os
import sys

import build
import errors
import icode
from icode import (
    BasicBlock, SetRI, SetRR, SetRNone, IfOp, BinOp, Goto, Return, Opcode,
    CallDirect, FuncIcode, UnaryOp
)
import transform


INDENT = 4


# Operator flags
OVERFLOW_CHECK_3_ARGS = 1
SHR_OPERAND = 2
CLEAR_LSB = 4


class CGenerator:
    """Translate icode to C."""
    
    FuncIcode func
    
    void __init__(self):
        self.out = <str> []
        self.prolog = ['#include "mypy.h"\n']
        self.indent = 0
        self.frame_size = 0
        # Count temp labels.
        self.num_labels = 0
    
    void generate_function(self, str name, FuncIcode func):
        # Initialize function-specific state information.
        self.func = func
        self.num_labels = 0
        self.frame_size = func.num_registers

        # Add function definition and opening brace.
        header = 'MValue %s(MEnv *e)' % name
        self.emit(header)
        self.emit('{')

        # Add function declaration.
        self.prolog.append('%s;\n' % header)

        # Generate code that updates and checks the stack pointer.
        self.emit('MValue t;')
        self.emit('MValue *frame = e->frame;')
        self.emit('e->frame = frame + %d;' % self.frame_size)
        self.emit('if (e->frame >= e->stack_top)')
        self.emit('    abort();') # Dummy handler; should raise an exception

        # Geneate code that initializes the stack frame. The gc must not see
        # uninitialized values.
        for i in range(func.num_args, self.frame_size):
            self.emit('frame[%d] = 0;' % i)

        # Translate function body, one basic block at a time.
        for b in func.blocks:
            self.emit('%s:' % label(b.label))
            for op in b.ops:
                self.opcode(op)

        self.emit('}')

    int_conditionals = {
        '==': 'MShortEq',
        '!=': 'MShortNe',
        '<': 'MShortLt',
        '<=': 'MShortLe',
        '>': 'MShortGt',
        '>=': 'MShortGe'
    }

    int_arithmetic = {
        '+': ('+', 'MIsAddOverflow', 'MIntAdd', OVERFLOW_CHECK_3_ARGS),
        '-': ('-', 'MIsSubOverflow', 'MIntSub', OVERFLOW_CHECK_3_ARGS),
        '*': ('*', 'MIsPotentialMulOverflow', 'MIntMul', SHR_OPERAND),
        '//': ('/', 'MIsPotentialFloorDivOverflow', 'MIntFloorDiv',
               SHR_OPERAND | CLEAR_LSB),
        '%': ('%', 'MIsPotentialModOverflow', 'MIntMod', 0),
        '&': ('&', None, 'MIntAnd', 0),
        '|': ('|', None, 'MIntAnd', 0),
        '^': ('^', None, 'MIntAnd', 0),
        '<<': ('<<', 'MIsShlOverflow', 'MIntShl', SHR_OPERAND),
        '>>': ('>>', 'MIsShrOverflow', 'MIntShr', SHR_OPERAND | CLEAR_LSB)
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
        op, overflow, opfn, flags = self.int_arithmetic[opcode.op]
        if flags & SHR_OPERAND:
            operation = '%s %s (%s >> 1)' % (left, op, right)
        else:
            operation = '%s %s %s' % (left, op, right)
        if flags & CLEAR_LSB:
            operation = '(%s) & ~1' % operation
        if flags & OVERFLOW_CHECK_3_ARGS:
            # Overflow check needs third argument (operation result).
            label = self.label()
            self.emit('if (MIsShort(%s) && MIsShort(%s)) {' % (left, right))
            self.emit(  't = %s;' % operation)
            self.emit(  'if (%s(t, %s, %s))' % (overflow, left, right))
            self.emit(  '    goto %s;' % label)
            self.emit('} else {')
            self.emit('%s:' % label)
            self.emit(  't = %s(e, %s, %s);' % (opfn, left, right))
            self.emit_error_check('t')
            self.emit('}')
            self.emit('%s = t;' % target)
        elif overflow:
            # Overflow check needs only 2 operands.
            self.emit('if (MIsShort(%s) && MIsShort(%s) && !%s(%s, %s))' %
                      (left, right, overflow, left, right))
            self.emit('    %s = %s;' % (target, operation))
            self.emit('else {')
            self.emit(  '%s = %s(e, %s, %s);' % (target, opfn, left, right))
            self.emit_error_check(target)
            self.emit('}')
        else:
            # No overflow check needed.
            self.emit('if (MIsShort(%s) && MIsShort(%s))' % (left, right))
            self.emit('    %s = %s;' % (target, operation))
            self.emit('else {')
            self.emit(  '%s = %s(e, %s, %s);' % (target, opfn, left, right))
            self.emit_error_check(target)
            self.emit('}')

    void opcode(self, UnaryOp opcode):
        target = reg(opcode.target)
        operand = reg(opcode.operand)
        if opcode.op == '-':
            self.emit('if (MIsShort(%s) && %s != M_SHORT_MIN)' % (
                operand, operand))
            self.emit('    %s = -%s;' % (target, operand))
            self.emit('else {')
            self.emit('    %s = MIntUnaryMinus(e, %s);' % (target, operand))
            self.emit_error_check(target)
            self.emit('}')
        elif opcode.op == '~':
            self.emit('if (MIsShort(%s))' % operand)
            self.emit('    %s = ~%s & ~1;' % (target, operand))
            self.emit('else {')
            self.emit('    %s = MIntInvert(e, %s);' % (target, operand))
            self.emit_error_check(target)
            self.emit('}')
        else:
            raise NotImplementedError('UnaryOp %s' % opcode.op)

    void opcode(self, Goto opcode):
        self.emit('goto %s;' % label(opcode.next_block.label))

    void opcode(self, Return opcode):
        self.emit_return(reg(opcode.retval))

    void opcode(self, CallDirect opcode):
        for i, arg in enumerate(opcode.args):
            self.emit('%s = %s;' % (reg(self.frame_size + i), reg(arg)))
        target = reg(opcode.target)
        self.emit('t = M%s(e);' % opcode.func)
        self.emit('if (t == MError)')
        self.emit('    return MError;')
        self.emit('%s = t;' % target)

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
        self.emit('e->frame = frame;')
        self.emit('return %s;' % retval)

    void emit_error_check(self, str value):
        self.emit('if (%s == MError) {' % value)
        self.emit_return('MError')
        self.emit('}')

    str label(self):
        n = self.num_labels
        self.num_labels = n + 1
        return 'T%d' % n


str reg(int n):
    return 'frame[%d]' % n


str label(int n):
    return 'L%d' % n


str operand(int n, int kind):
    if kind == icode.INT_KIND:
        return str(n * 2)
    else:
        return reg(n)


MAIN_FRAGMENT = '''
int main(int argc, char **argv) {
    MValue stack[1024];
    MEnv env;
    env.frame = stack;
    env.stack_top = stack + 1024 - 16; // Reserve 16 entries for arguments
    M__init(&env);
    return 0;
}
'''


if __name__ == '__main__':
    program = sys.argv[1]
    text = open(program).read()
    
    try:
        # Compile the input program to a binary via C.
        result = build.build(program_text=text,
                             program_path=program,
                             target=build.C,
                             alt_lib_path='lib')
    except errors.CompileError as e:
        for s in e.messages:
            sys.stderr.write(s + '\n')
        sys.exit(1)
