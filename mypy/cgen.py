"""Generate C code from icode."""

import os

from typing import Undefined, List, Dict, overload

from mypy import errors
from mypy import icode
from mypy.icode import (
    BasicBlock, SetRI, SetRR, SetRNone, IfOp, BinOp, Goto, Return, Opcode,
    CallDirect, CallMethod, FuncIcode, UnaryOp, SetGR, SetRG, Construct,
    SetAttr, GetAttr, IfR
)
from mypy.nodes import TypeInfo, FuncBase
from mypy import transform


INDENT = 4


# Operator flags
OVERFLOW_CHECK_3_ARGS = 1
SHR_OPERAND = 2
CLEAR_LSB = 4


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


class CGenerator:
    """Translate icode to C."""
    
    func = Undefined(FuncIcode)

    def __init__(self) -> None:
        self.prolog = ['#include "mypy.h"\n']
        self.types = [] # type: List[str]
        self.out = [] # type: List[str]
        self.indent = 0
        self.frame_size = 0
        self.global_vars = {} # type: Dict[str, int]
        self.classes = {} # type: Dict[TypeInfo, ClassRepresentation]
        # Count temp labels.
        self.num_labels = 0

    def output(self) -> List[str]:
        result = self.prolog[:]
        result.append('MValue Mglobals[%d];' % max(len(self.global_vars), 1))
        result.append('\n')
        result.extend(self.types)
        result.extend(self.out)
        result.append(MAIN_FRAGMENT)
        return result
    
    def generate_function(self, name: str, func: FuncIcode) -> None:
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

    @overload
    def opcode(self, opcode: SetRI) -> None:
        self.emit('%s = %d;' % (reg(opcode.target), 2 * opcode.intval))

    @overload
    def opcode(self, opcode: SetRR) -> None:
        self.emit('%s = %s;' % (reg(opcode.target), reg(opcode.source)))

    @overload
    def opcode(self, opcode: SetRNone) -> None:
        self.emit('%s = MNone;' % reg(opcode.target))

    @overload
    def opcode(self, opcode: SetGR) -> None:
        self.emit('%s = %s;' % (self.globalvar(opcode.target),
                                reg(opcode.source)))

    @overload
    def opcode(self, opcode: SetRG) -> None:
        self.emit('%s = %s;' % (reg(opcode.target),
                                self.globalvar(opcode.source)))

    @overload
    def opcode(self, opcode: IfOp) -> None:
        left = operand(opcode.left, opcode.left_kind)
        right = operand(opcode.right, opcode.right_kind)
        op = self.int_conditionals[opcode.op]
        self.emit('if (%s(%s, %s))' % (op, left, right))
        self.emit('    goto %s;' % (label(opcode.true_block.label)))
        self.emit('else')
        self.emit('    goto %s;' % (label(opcode.false_block.label)))

    @overload
    def opcode(self, opcode: IfR) -> None:
        op = '!='
        if opcode.negated:
            op = '=='
        self.emit('if (%s %s MNone)' % (reg(opcode.value), op))
        self.emit('    goto %s;' % (label(opcode.true_block.label)))
        self.emit('else')
        self.emit('    goto %s;' % (label(opcode.false_block.label)))

    @overload
    def opcode(self, opcode: BinOp) -> None:
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

    @overload
    def opcode(self, opcode: UnaryOp) -> None:
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

    @overload
    def opcode(self, opcode: Goto) -> None:
        self.emit('goto %s;' % label(opcode.next_block.label))

    @overload
    def opcode(self, opcode: Return) -> None:
        self.emit_return(reg(opcode.retval))

    @overload
    def opcode(self, opcode: CallDirect) -> None:
        for i, arg in enumerate(opcode.args):
            self.emit('%s = %s;' % (reg(self.frame_size + i), reg(arg)))
        self.direct_call(opcode.target, opcode.func)

    @overload
    def opcode(self, opcode: CallMethod) -> None:
        recv = reg(opcode.object)
        self.emit('%s = %s;' % (reg(self.frame_size), recv))
        for i, arg in enumerate(opcode.args):
            self.emit('%s = %s;' % (reg(self.frame_size + 1 + i), reg(arg)))
        target = reg(opcode.target)
        self.get_class_representation(opcode.type)
        rep = self.classes[opcode.type]
        method = opcode.method.replace('$', '_') # Simple name mangling.
        if opcode.static:
            self.direct_call(opcode.target, '%s_%s' % (opcode.type.name(),
                                                       method))
        else:
            vtable_index = rep.vtable_index[method]
            self.emit('t = MInvokeVirtual(e, %s, %d);' % (recv, vtable_index))
            self.emit('if (t == MError)')
            self.emit('    return MError;')
            self.emit('%s = t;' % reg(opcode.target))

    @overload
    def opcode(self, opcode: Construct) -> None:
        rep = self.get_class_representation(opcode.type)
        self.emit('t = MAlloc(e, sizeof(MInstanceHeader) + '
                  '%d * sizeof(MValue));' % len(rep.slotmap))
        self.emit('MInitInstance(t, &%s);' % rep.cname)
        self.emit('%s = t;' % reg(opcode.target))

    @overload
    def opcode(self, opcode: SetAttr) -> None:
        rep = self.get_class_representation(opcode.type)
        slot = rep.slotmap[opcode.attr]
        self.emit('MSetSlot(%s, %d, %s);' % (reg(opcode.object),
                                             slot, reg(opcode.source)))

    @overload
    def opcode(self, opcode: GetAttr) -> None:
        rep = self.get_class_representation(opcode.type)
        slot = rep.slotmap[opcode.attr]
        self.emit('%s = MGetSlot(%s, %d);' % (reg(opcode.target),
                                              reg(opcode.object), slot))

    @overload
    def opcode(self, opcode: Opcode) -> None:
        """Default case."""
        raise NotImplementedError(type(opcode))

    #
    # Helpers
    #

    def get_class_representation(self, cls: TypeInfo) -> 'ClassRepresentation':
        rep = self.classes.get(cls)
        if not rep:
            rep = self.generate_class(cls)
        return rep

    def generate_class(self, cls: TypeInfo) -> 'ClassRepresentation':
        if cls.bases:
            baserep = self.get_class_representation(cls.bases[0].type)
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
        self.emit_types('    "%s"' % cls.fullname())
        self.emit_types('};\n')
        
        return rep

    def direct_call(self, target: int, funcname: str) -> None:
        self.emit('t = M%s(e);' % funcname)
        self.emit('if (t == MError)')
        self.emit('    return MError;')
        self.emit('%s = t;' % reg(target))

    def emit(self, s: str) -> None:
        if '}' in s:
            self.indent -= INDENT
        indent = self.indent
        if s.endswith(':'):
            indent -= INDENT
        self.out.append(' ' * indent + s + '\n')
        if '{' in s:
            self.indent += INDENT

    def emit_return(self, retval: str) -> None:
        self.emit('e->frame = frame;')
        self.emit('return %s;' % retval)

    def emit_error_check(self, value: str) -> None:
        self.emit('if (%s == MError) {' % value)
        self.emit_return('MError')
        self.emit('}')

    def emit_prolog(self, s: str) -> None:
        self.prolog.append(s + '\n')

    def emit_types(self, s: str) -> None:
        self.types.append(s + '\n')

    def label(self) -> str:
        n = self.num_labels
        self.num_labels = n + 1
        return 'T%d' % n

    def globalvar(self, name: str) -> str:
        num = self.global_vars.get(name, -1)
        if num < 0:
            num = len(self.global_vars)
            self.global_vars[name] = num
        return 'Mglobals[%d]' % num


def reg(n: int) -> str:
    return 'frame[%d]' % n


def label(n: int) -> str:
    return 'L%d' % n


def operand(n: int, kind: int) -> str:
    if kind == icode.INT_KIND:
        return str(n * 2)
    else:
        return reg(n)


class ClassRepresentation:
    """Description of the runtime representation of a mypy class."""
    # TODO add methods
    # TODO add base class

    cname = ''
    fullname = ''
    
    slotmap = Undefined(Dict[str, int])
    
    # Map method name to/from vtable index
    vtable_index = Undefined(Dict[str, int])
    
    defining_class = Undefined(Dict[str, str])
    
    vtable_methods = Undefined(List[str])

    def __init__(self, type: TypeInfo, base: 'ClassRepresentation') -> None:
        self.cname = 'MR_%s' % type.name()
        self.fullname = type.fullname()
        self.slotmap = {}
        self.vtable_index = {}
        self.defining_class = {}
        self.vtable_methods = []
        if base:
            self.inherit_from_base(base)
        for m in sorted(type.names):
            if isinstance(type.names[m].node, FuncBase):
                self.add_method(m, type)
            else:
                self.slotmap[m] = len(self.slotmap)
                self.add_method('_' + m, type)    # Getter TODO refactor
                self.add_method('set_' + m, type) # Setter # TODO refactor

    def add_method(self, method: str, defining_class: TypeInfo) -> None:
        self.defining_class[method] = defining_class.name()
        if method not in self.vtable_index:
            self.vtable_index[method] = len(self.vtable_methods)
            self.vtable_methods.append(method)

    def inherit_from_base(self, base: 'ClassRepresentation') -> None:
        # TODO use dict.update
        for k, v in base.vtable_index.items():
            self.vtable_index[k] = v
        self.vtable_methods.extend(base.vtable_methods)
        for k, v in base.slotmap.items():
            self.slotmap[k] = v
        for k, n in base.defining_class.items():
            self.defining_class[k] = n
