"""Generate C code from icode."""

import os
import sys

import build
import errors
import icode
from icode import (
    BasicBlock, SetRI, SetRR, SetRNone, IfOp, BinOp, Goto, Return, Opcode,
    CallDirect, CallMethod, FuncIcode, UnaryOp, SetGR, SetRG, Construct,
    SetAttr, GetAttr, IfR
)
from nodes import TypeInfo
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
        self.prolog = ['#include "mypy.h"\n']
        self.types = <str> []
        self.out = <str> []
        self.indent = 0
        self.frame_size = 0
        self.global_vars = <str, int> {}
        self.classes = <TypeInfo, ClassRepresentation> {}
        # Count temp labels.
        self.num_labels = 0

    str[] output(self):
        result = self.prolog[:]
        result.append('MValue Mglobals[%d];' % max(len(self.global_vars), 1))
        result.append('\n')
        result.extend(self.types)
        result.extend(self.out)
        result.append(MAIN_FRAGMENT)
        return result
    
    void generate_function(self, str name, FuncIcode func):
        # Initialize function-specific state information.
        self.func = func
        self.num_labels = 0
        self.frame_size = func.num_registers

        # Simplistic name mangling.
        name = name.replace('.', '_')
        name = name.replace('$', '_')
        
        # Add function definition and opening brace.
        header = 'MValue %s(MEnv *e)' % name
        self.emit(header)
        self.emit('{')

        # Add function declaration.
        self.emit_prolog('%s;\n' % header)

        # Generate code that updates and checks the stack pointer.
        self.emit('MValue t;')
        self.emit('MValue *frame = e->frame;')
        self.emit('e->frame = frame + %d;' % self.frame_size)
        self.emit('if (e->frame >= e->stack_top)')
        self.emit('    abort();') # Dummy handler; should raise an exception

        # Geneate code that initializes the stack frame. The gc must not see
        # uninitialized values.
        for i in range(func.num_args, self.frame_size):
            if func.register_types[i] == icode.INT:
                self.emit('frame[%d] = 0;' % i)
            else:
                self.emit('frame[%d] = MNone;' % i)

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

    void opcode(self, SetGR opcode):
        self.emit('%s = %s;' % (self.globalvar(opcode.target),
                                reg(opcode.source)))

    void opcode(self, SetRG opcode):
        self.emit('%s = %s;' % (reg(opcode.target),
                                self.globalvar(opcode.source)))

    void opcode(self, IfOp opcode):
        left = operand(opcode.left, opcode.left_kind)
        right = operand(opcode.right, opcode.right_kind)
        op = self.int_conditionals[opcode.op]
        self.emit('if (%s(%s, %s))' % (op, left, right))
        self.emit('    goto %s;' % (label(opcode.true_block.label)))
        self.emit('else')
        self.emit('    goto %s;' % (label(opcode.false_block.label)))

    void opcode(self, IfR opcode):
        op = '!='
        if opcode.negated:
            op = '=='
        self.emit('if (%s %s MNone)' % (reg(opcode.value), op))
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
        self.direct_call(opcode.target, opcode.func)

    void opcode(self, CallMethod opcode):
        recv = reg(opcode.object)
        self.emit('%s = %s;' % (reg(self.frame_size), recv))
        for i, arg in enumerate(opcode.args):
            self.emit('%s = %s;' % (reg(self.frame_size + 1 + i), reg(arg)))
        target = reg(opcode.target)
        self.get_class_representation(opcode.type)
        rep = self.classes[opcode.type]
        method = opcode.method.replace('$', '_') # Simple name mangling.
        if method == '__init__':
            self.direct_call(opcode.target, '%s_%s' % (opcode.type.name(),
                                                       method))
        else:
            vtable_index = rep.vtable_index[method]
            self.emit('t = MInvokeVirtual(e, %s, %d);' % (recv, vtable_index))
            self.emit('if (t == MError)')
            self.emit('    return MError;')
            self.emit('%s = t;' % reg(opcode.target))

    void opcode(self, Construct opcode):
        rep = self.get_class_representation(opcode.type)
        self.emit('t = MAlloc(e, sizeof(MInstanceHeader) + '
                  '%d * sizeof(MValue));' % len(rep.slotmap))
        self.emit('MInitInstance(t, &%s);' % rep.cname)
        self.emit('%s = t;' % reg(opcode.target))

    void opcode(self, SetAttr opcode):
        rep = self.get_class_representation(opcode.type)
        slot = rep.slotmap[opcode.attr]
        self.emit('MSetSlot(%s, %d, %s);' % (reg(opcode.object),
                                             slot, reg(opcode.source)))

    void opcode(self, GetAttr opcode):
        rep = self.get_class_representation(opcode.type)
        slot = rep.slotmap[opcode.attr]
        self.emit('%s = MGetSlot(%s, %d);' % (reg(opcode.target),
                                              reg(opcode.object), slot))

    void opcode(self, Opcode opcode):
        """Default case."""
        raise NotImplementedError(type(opcode))

    #
    # Helpers
    #

    ClassRepresentation get_class_representation(self, TypeInfo cls):
        rep = self.classes.get(cls)
        if not rep:
            if cls.base:
                baserep = self.get_class_representation(cls.base)
            else:
                baserep = None
            rep = ClassRepresentation(cls, baserep)
            self.classes[cls] = rep

            # Emit vtable.
            vtable = 'MVT_%s' % cls.name()
            self.emit_types('MFunction %s[] = {' % vtable)
            for m in rep.vtable_methods:
                defining_class = rep.defining_class[m]
                self.emit_types('    M%s_%s,' % (defining_class, m))
            self.emit_types('}; /* %s */' % vtable)

            # Emit type runtime info.
            self.emit_types('MTypeRepr %s = {' % rep.cname)
            self.emit_types('    %s,' % vtable)
            self.emit_types('    0,')
            self.emit_types('    "%s"' % cls.full_name())
            self.emit_types('};\n')
        return rep

    void direct_call(self, int target, str funcname):
        self.emit('t = M%s(e);' % funcname)
        self.emit('if (t == MError)')
        self.emit('    return MError;')
        self.emit('%s = t;' % reg(target))

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

    void emit_prolog(self, str s):
        self.prolog.append(s + '\n')

    void emit_types(self, str s):
        self.types.append(s + '\n')

    str label(self):
        n = self.num_labels
        self.num_labels = n + 1
        return 'T%d' % n

    str globalvar(self, str name):
        num = self.global_vars.get(name, -1)
        if num < 0:
            num = len(self.global_vars)
            self.global_vars[name] = num
        return 'Mglobals[%d]' % num


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


class ClassRepresentation:
    """Description of the runtime representation of a mypy class."""
    # TODO add methods
    # TODO add base class

    str cname
    str full_name
    dict<str, int> slotmap
    # Map method name to/from vtable index
    dict<str, int> vtable_index
    dict<str, str> defining_class
    str[] vtable_methods

    void __init__(self, TypeInfo type, ClassRepresentation base):
        self.cname = 'MR_%s' % type.name()
        self.full_name = type.full_name()
        self.slotmap = {}
        self.vtable_index = {}
        self.defining_class = {}
        self.vtable_methods = []
        if base:
            self.inherit_from_base(base)
        for m in sorted(type.methods):
            self.add_method(m, type)
        for v in type.vars.keys():
            self.slotmap[v] = len(self.slotmap)
            self.add_method('_' + v, type)    # Getter TODO refactor
            self.add_method('set_' + v, type) # Setter # TODO refactor

    void add_method(self, str method, TypeInfo defining_class):
        self.defining_class[method] = defining_class.name()
        if method not in self.vtable_index:
            self.vtable_index[method] = len(self.vtable_methods)
            self.vtable_methods.append(method)

    void inherit_from_base(self, ClassRepresentation base):
        # TODO use dict.update
        for k, v in base.vtable_index.items():
            self.vtable_index[k] = v
        self.vtable_methods.extend(base.vtable_methods)
        for k, v in base.slotmap.items():
            self.slotmap[k] = v
        for k, n in base.defining_class.items():
            self.defining_class[k] = n


if __name__ == '__main__':
    program = sys.argv[1]
    text = open(program).read()
    
    try:
        # Compile the input program to a binary via C.
        result = build.build(program_text=text,
                             program_path=program,
                             target=build.C)
    except errors.CompileError as e:
        for s in e.messages:
            sys.stderr.write(s + '\n')
        sys.exit(1)
