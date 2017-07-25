from typing import List

from mypyc.common import PREFIX, NATIVE_PREFIX, REG_PREFIX
from mypyc.ops import (
    OpVisitor, Environment, Label, Register, RTType, FuncIR, Goto, Branch, Return, PrimitiveOp,
    Assign, LoadInt, IncRef, DecRef, Call, Box, Unbox, OP_BINARY
)


class Emitter:
    def __init__(self, env: Environment) -> None:
        self.env = env
        self.declarations = []  # type: List[str]
        self.fragments = []  # type: List[str]

    def all_fragments(self) -> List[str]:
        return self.declarations + self.fragments

    def label(self, label: Label) -> str:
        return 'CPyL%d' % label

    def reg(self, reg: Register) -> str:
        name = self.env.names[reg]
        return REG_PREFIX + name

    def emit(self, string: str) -> None:
        self.fragments.append(string)

    def emit_declaration(self, line: str, indent: int = 4) -> None:
        self.declarations.append(indent * ' ' + line + '\n')

    def emit_line(self, line: str, indent: int = 4) -> None:
        self.fragments.append(indent * ' ' + line + '\n')

    def emit_lines(self, *lines: str, indent: int = 4) -> None:
        for line in lines:
            self.emit_line(line, indent=indent)

    def emit_label(self, label: Label) -> None:
        self.emit_line('{}:'.format(self.label(label)), indent=0)


class EmitterVisitor(OpVisitor):
    def __init__(self, emitter: Emitter) -> None:
        self.emitter = emitter
        self.env = self.emitter.env
        self.temp_counter = 0

    def visit_goto(self, op: Goto) -> None:
        self.emit_line('goto %s;' % self.label(op.label))

    BRANCH_OP_MAP = {
        Branch.INT_EQ: 'CPyTagged_IsEq',
        Branch.INT_NE: 'CPyTagged_IsNe',
        Branch.INT_LT: 'CPyTagged_IsLt',
        Branch.INT_LE: 'CPyTagged_IsLe',
        Branch.INT_GT: 'CPyTagged_IsGt',
        Branch.INT_GE: 'CPyTagged_IsGe',
    }

    def visit_branch(self, op: Branch) -> None:
        left = self.reg(op.left)
        right = self.reg(op.right)
        fn = EmitterVisitor.BRANCH_OP_MAP[op.op]
        neg = '!' if op.negated else ''
        self.emit_lines('if (%s%s(%s, %s))' % (neg, fn, left, right),
                        '    goto %s;' % self.label(op.true),
                        'else',
                        '    goto %s;' % self.label(op.false))

    def visit_return(self, op: Return) -> None:
        typ = self.type(op.reg)
        assert typ.name in ('bool', 'int', 'list', 'None')
        regstr = self.reg(op.reg)
        self.emit_line('return %s;' % regstr)

    OP_MAP = {
        PrimitiveOp.INT_ADD: 'CPyTagged_Add',
        PrimitiveOp.INT_SUB: 'CPyTagged_Subtract',
        PrimitiveOp.INT_MUL: 'CPyTagged_Multiply',
        PrimitiveOp.INT_DIV: 'CPyTagged_FloorDivide',
        PrimitiveOp.INT_MOD: 'CPyTagged_Remainder',
    }

    UNARY_OP_MAP = {
        PrimitiveOp.INT_NEG: 'CPy_NegateInt',
    }

    def visit_primitive_op(self, op: PrimitiveOp) -> None:
        dest = self.reg(op.dest) if op.dest is not None else None
        if op.desc.kind == OP_BINARY:
            assert dest is not None
            left = self.reg(op.args[0])
            right = self.reg(op.args[1])
            if op.desc in EmitterVisitor.OP_MAP:
                fn = EmitterVisitor.OP_MAP[op.desc]
                self.emit_line('%s = %s(%s, %s);' % (dest, fn, left, right))
            elif op.desc is PrimitiveOp.LIST_GET:
                self.emit_lines('%s = CPyList_GetItem(%s, %s);' % (dest, left, right),
                                'if (!%s)' % dest,
                                '    abort();')
            elif op.desc is PrimitiveOp.LIST_REPEAT:
                temp = self.temp_name()
                self.emit_declaration('long long %s;' % temp)
                self.emit_lines(
                    '%s = CPyTagged_AsLongLong(%s);' % (temp, right),
                    'if (%s == -1 && PyErr_Occurred())' % temp,
                    '    abort();',
                    '%s = PySequence_Repeat(%s, %s);' % (dest, left, temp),
                    'if (!%s)' % dest,
                    '    abort();')
            else:
                assert False, op.desc
        elif op.desc is PrimitiveOp.LIST_SET:
            assert dest is None
            self.emit_lines('if (!CPyList_SetItem(%s, %s, %s))' % (self.reg(op.args[0]),
                                                                   self.reg(op.args[1]),
                                                                   self.reg(op.args[2])),
                            '    abort();')
        elif op.desc is PrimitiveOp.NONE:
            self.emit_lines('%s = Py_None;' % dest,
                            'Py_INCREF(%s);' % dest)

        elif op.desc is PrimitiveOp.NEW_LIST:
            self.emit_line('%s = PyList_New(%d); ' % (dest, len(op.args)))
            for i, arg in enumerate(op.args):
                reg = self.reg(arg)
                self.emit_line('Py_INCREF(%s);' % reg)
                self.emit_line('PyList_SET_ITEM(%s, %s, %s);' % (dest, i, reg))
        elif op.desc is PrimitiveOp.LIST_APPEND:
            self.emit_lines(
                'if (PyList_Append(%s, %s) == -1)' % (self.reg(op.args[0]), self.reg(op.args[1])),
                '    abort();')
        else:
            assert len(op.args) == 1
            assert dest is not None
            src = self.reg(op.args[0])
            if op.desc is PrimitiveOp.LIST_LEN:
                temp = self.temp_name()
                self.emit_declaration('long long %s;' % temp)
                self.emit_line('%s = PyList_GET_SIZE(%s);' % (temp, src))
                self.emit_line('%s = CPyTagged_ShortFromLongLong(%s);' % (dest, temp))
            else:
                # Simple unary op
                fn = EmitterVisitor.UNARY_OP_MAP[op.desc]
                self.emit_line('%s = %s(%s);' % (dest, fn, src))

    def visit_assign(self, op: Assign) -> None:
        dest = self.reg(op.dest)
        src = self.reg(op.src)
        self.emit_line('%s = %s;' % (dest, src))

    def visit_load_int(self, op: LoadInt) -> None:
        dest = self.reg(op.dest)
        self.emit_line('%s = %d;' % (dest, op.value * 2))

    def visit_call(self, op: Call) -> None:
        if op.dest is not None:
            dest = self.reg(op.dest) + ' = '
        else:
            dest = ''
        args = ', '.join(self.reg(arg) for arg in op.args)
        self.emit_line('%s%s%s(%s);' % (dest, NATIVE_PREFIX, op.fn, args))

    def visit_inc_ref(self, op: IncRef) -> None:
        dest = self.reg(op.dest)
        if op.target_type.name == 'int':
            self.emit_line('CPyTagged_IncRef(%s);' % dest)
        elif op.target_type.name == 'bool':
            return
        else:
            self.emit_line('Py_INCREF(%s);' % dest)

    def visit_dec_ref(self, op: DecRef) -> None:
        dest = self.reg(op.dest)
        if op.target_type.name == 'int':
            self.emit_line('CPyTagged_DecRef(%s);' % dest)
        elif op.target_type.name == 'bool':
            return
        else:
            self.emit_line('Py_DECREF(%s);' % dest)

    def visit_box(self, op: Box) -> None:
        src = self.reg(op.src)
        dest = self.reg(op.dest)
        if op.type.name == 'int':
            self.emit_lines('%s = CPyTagged_AsObject(%s);' % (dest, src),
                            'if (%s == NULL)' % dest,
                            '    abort();')
        elif op.type.name == 'bool':
            self.emit_line('%s = PyBool_FromLong(%s);' % (dest, src))
        else:
            assert False, "invalid box"

    def visit_unbox(self, op: Unbox) -> None:
        src = self.reg(op.src)
        dest = self.reg(op.dest)
        if op.type.name == 'int':
            self.emit_lines('if (PyLong_Check(%s))' % src,
                            '    %s = CPyTagged_FromObject(%s);' % (dest, src),
                            'else',
                            '    abort();')
        elif op.type.name == 'bool':
            self.emit_lines(
                'if (PyBool_Check(%s))' % src,
                '    %s = CPyObject_IsTrue(%s);' % (dest, src),
                'else'
                '    abort();'
            )
        else:
            assert False, "invalid unbox"

    # Helpers

    def label(self, label: Label) -> str:
        return self.emitter.label(label)

    def reg(self, reg: Register) -> str:
        return self.emitter.reg(reg)

    def type(self, reg: Register) -> RTType:
        return self.env.types[reg]

    def emit(self, string: str) -> None:
        self.emitter.emit(string)

    def emit_line(self, line: str, indent: int = 4) -> None:
        self.emitter.emit_line(line, indent)

    def emit_lines(self, *lines: str, indent: int = 4) -> None:
        self.emitter.emit_lines(*lines, indent=indent)

    def emit_declaration(self, line: str, indent: int = 4) -> None:
        self.emitter.emit_declaration(line, indent)

    def temp_name(self) -> str:
        self.temp_counter += 1
        return '__tmp%d' % self.temp_counter


def native_function_header(fn: FuncIR) -> str:
    # TODO: Don't hard code argument and return value types
    args = []
    for arg in fn.args:
        args.append('{}{}{}'.format(arg.type.ctype, REG_PREFIX, arg.name))

    return 'static {ret_type} {prefix}{name}({args})'.format(
        ret_type=rttype_to_ctype(fn.ret_type),
        prefix=NATIVE_PREFIX,
        name=fn.name,
        args=', '.join(args))


def generate_c_for_function(fn: FuncIR) -> List[str]:
    emitter = Emitter(fn.env)
    visitor = EmitterVisitor(emitter)

    emitter.emit_declaration('{} {{'.format(native_function_header(fn)), indent=0)

    for i in range(len(fn.args), fn.env.num_regs()):
        ctype = rttype_to_ctype(fn.env.types[i])
        emitter.emit_declaration('{ctype} {prefix}{name};'.format(ctype=ctype,
                                                                  prefix=REG_PREFIX,
                                                                  name=fn.env.names[i]))

    for block in fn.blocks:
        emitter.emit_label(block.label)
        for op in block.ops:
            op.accept(visitor)

    emitter.emit_line('}', indent=0);

    return emitter.all_fragments()


def wrapper_function_header(fn: FuncIR) -> str:
    return 'static PyObject *{prefix}{name}(PyObject *self, PyObject *args, PyObject *kw)'.format(
            prefix=PREFIX,
            name=fn.name)


def generate_wrapper_function(fn: FuncIR) -> List[str]:
    """Generates a CPython-compatible wrapper function for a native function.
    
    In particular, this handles unboxing the arguments, calling the native function, and
    then boxing the return value.
    """
    result = []
    result.append('{} {{'.format(wrapper_function_header(fn)))
    arg_names = ''.join('"{}", '.format(arg.name) for arg in fn.args)
    result.append('    static char *kwlist[] = {{{}0}};'.format(arg_names))
    for arg in fn.args:
        result.append('    PyObject *obj_{};'.format(arg.name))
    arg_spec = 'O' * len(fn.args)
    arg_ptrs = ''.join(', &obj_{}'.format(arg.name) for arg in fn.args)
    result.append('    if (!PyArg_ParseTupleAndKeywords(args, kw, "{}:f", kwlist{})) {{'.format(
        arg_spec, arg_ptrs))
    result.append('        return NULL;')
    result.append('    }')
    for arg in fn.args:
        check = generate_arg_check(arg.name, arg.type)
        result.extend(check)
    native_args = ', '.join('arg_{}'.format(arg.name) for arg in fn.args)
    if fn.ret_type.name == 'int':
        result.append('    CPyTagged retval = CPyDef_{}({});'.format(fn.name, native_args))
        result.append('    if (retval == CPY_INT_ERROR_VALUE && PyErr_Occurred()) {')
        result.append('        return NULL; // TODO: Add traceback entry?')
        result.append('    }')
        result.append('    return CPyTagged_AsObject(retval);')
    elif fn.ret_type.name == 'bool':
        # The Py_RETURN macros return the correct PyObject * with reference count handling.
        result.append('    char retval = {}{}({});'.format(NATIVE_PREFIX, fn.name, native_args))
        result.append('    if(retval)')
        result.append('        Py_RETURN_TRUE;')
        result.append('    else')
        result.append('        Py_RETURN_FALSE;')
    else:
        result.append('     return CPyDef_{}({});'.format(fn.name, native_args))
        # TODO: Tracebacks?
    result.append('}')
    return result


def generate_arg_check(name: str, typ: RTType) -> List[str]:
    """Insert a runtime check for argument and unbox if necessary.

    The object is named PyObject *obj_{}. This is expected to generate
    a value of name arg_{} (unboxed if necessary). For each primitive a runtime
    check ensures the correct type.
    """
    if typ.name == 'int':
        return [
            '    CPyTagged arg_{} = CPyTagged_FromObject(obj_{});'.format(name, name),
            '    if (arg_{} == CPY_INT_ERROR_VALUE) {{'.format(name),
            '        return NULL; // TODO: Add traceback entry?',
            '    }',
        ]
    elif typ.name == 'bool':
        return [
            '    if(!PyBool_Check(obj_{}))'.format(name),
            '        return NULL; // TODO: Add traceback entry?',
            '    char arg_{} = PyObject_IsTrue(obj_{});'.format(name, name)
        ]
    elif typ.name == 'list':
        return [
            '    PyObject *arg_{};'.format(name),
            '    if (PyList_Check(obj_{}))'.format(name),
            '        arg_{} = obj_{};'.format(name, name),
            '    else',
            '        return NULL; // TODO: Add traceback entry?',
        ]
    else:
        assert False, typ


def rttype_to_ctype(typ: RTType) -> str:
    if typ.name == 'int':
        return 'CPyTagged'
    elif typ.name == 'bool':
        return 'char'
    else:
        return 'PyObject *'
