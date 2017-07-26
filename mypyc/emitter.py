from typing import List, Set, Dict

from mypyc.common import PREFIX, NATIVE_PREFIX, REG_PREFIX
from mypyc.ops import (
    OpVisitor, Environment, Label, Register, RTType, FuncIR, Goto, Branch, Return, PrimitiveOp,
    Assign, LoadInt, IncRef, DecRef, Call, Box, Unbox, TupleRTType, TupleGet, OP_BINARY
)


class HeaderDeclaration:
    def __init__(self, dependencies: Set[str], body: List[str]) -> None:
        self.dependencies = dependencies
        self.body = body


class MarkedDeclaration:
    """Add a mark, useful for topological sort.
    """
    def __init__(self, declaration: HeaderDeclaration, mark: bool) -> None:
        self.declaration = declaration
        self.mark = False


class CodeGenerator:
    def __init__(self) -> None:
        self.temp_counter = 0
        self.declarations = {} # type: Dict[str, HeaderDeclaration]
        self.header_declarations = [] # type: List[str]

    def toposort_declarations(self) -> List[HeaderDeclaration]:
        result = []
        marked_declarations = { k: MarkedDeclaration(v, False) for k, v in self.declarations.items() }

        def _toposort_visit(name):
            decl = marked_declarations[name]
            if decl.mark:
                return

            for child in decl.declaration.dependencies:
                _toposort_visit(child)

            result.append(decl.declaration)
            decl.mark = True

        for name, marked_declaration in marked_declarations.items():
           _toposort_visit(name)

        return result

    def declare_tuple_struct(self, tuple_type: TupleRTType) -> None:
        if tuple_type.struct_name not in self.declarations:
            dependencies = set()
            for typ in tuple_type.types:
                # XXX other types might eventually need similar behavior
                if isinstance(typ, TupleRTType):
                    dependencies.add(typ.struct_name)

            self.declarations[tuple_type.struct_name] = HeaderDeclaration(
                dependencies,
                tuple_type.get_c_declaration(),
            )

    def temp_name(self) -> str:
        self.temp_counter += 1
        return '__tmp%d' % self.temp_counter

    def generate_c_for_function(self, fn: FuncIR) -> List[str]:
        emitter = Emitter(self, fn.env)
        visitor = EmitterVisitor(emitter)

        emitter.emit_declaration('{} {{'.format(native_function_header(fn)), indent=0)

        for i in range(len(fn.args), fn.env.num_regs()):
            ctype = fn.env.types[i].ctype
            emitter.emit_declaration('{ctype} {prefix}{name};'.format(ctype=ctype,
                                                                      prefix=REG_PREFIX,
                                                                      name=fn.env.names[i]))

        for block in fn.blocks:
            emitter.emit_label(block.label)
            for op in block.ops:
                op.accept(visitor)

        emitter.emit_line('}', indent=0);

        return emitter.all_fragments()

    def generate_box(self, src: str, dest: str, typ: RTType, failure: str) -> List[str]:
        result = []
        if typ.name == 'int':
            result.append('    PyObject *{} = CPyTagged_AsObject({});'.format(dest, src))
        elif typ.name == 'bool':
            # The Py_RETURN macros return the correct PyObject * with reference count handling.
            result.append('    PyObject *{} = PyBool_FromLong({});'.format(dest, src))
        elif typ.name == 'tuple':
            assert isinstance(typ, TupleRTType)
            self.declare_tuple_struct(typ)
            result.append('    PyObject *{} = PyTuple_New({});'.format(dest, len(typ.types)))
            result.append('    if ({} == NULL) {{'.format(dest))
            result.append('    {}'.format(failure))
            result.append('    }')
            # TODO: Fail if dest is None
            for i in range(0, len(typ.types)):
                if not typ.supports_unbox:
                    result.append('    PyTuple_SetItem({}, {}, {}.f{}'.format(dest, i, src, i))
                else:
                    inner_name = self.temp_name()
                    result += self.generate_box('{}.f{}'.format(src, i), inner_name, typ.types[i], failure)
                    result.append('    PyTuple_SetItem({}, {}, {});'.format(dest, i, inner_name, i))

        return result


    def generate_wrapper_function(self, fn: FuncIR) -> List[str]:
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
            check = self.generate_arg_check(arg.name, arg.type)
            result.extend(check)
        native_args = ', '.join('arg_{}'.format(arg.name) for arg in fn.args)

        if fn.ret_type.supports_unbox:
            if fn.ret_type.name == 'int':
                result.append('    CPyTagged retval = CPyDef_{}({});'.format(fn.name, native_args))
                result.append('    if (retval == CPY_INT_ERROR_VALUE && PyErr_Occurred()) {')
                result.append('        return NULL; // TODO: Add traceback entry?')
                result.append('    }')
                result += self.generate_box('retval', 'retbox', fn.ret_type, 'return NULL;')
                # TODO: Decrease reference count of retval?
                result.append('    return retbox;')
            elif fn.ret_type.name == 'bool':
                # The Py_RETURN macros return the correct PyObject * with reference count handling.
                result.append('    char retval = {}{}({});'.format(NATIVE_PREFIX, fn.name, native_args))
                result += self.generate_box('retval', 'retbox', fn.ret_type, 'return NULL;')
                result.append('    return retbox;')
            elif fn.ret_type.name == 'tuple':
                result.append('    {}retval = {}{}({});'.format(fn.ret_type.ctype_spaced, NATIVE_PREFIX, fn.name, native_args))
                result += self.generate_box('retval', 'retbox', fn.ret_type, 'return NULL;')
                result.append('    return retbox;')
        else:
            # Any type that needs to be unboxed should be special cased, so fail if
            # we failed to do so.
            assert not fn.ret_type.supports_unbox
            result.append('     return CPyDef_{}({});'.format(fn.name, native_args))
            # TODO: Tracebacks?
        result.append('}')
        return result


    def generate_unbox(self, src: str, dest: str, typ: RTType, failure: str) -> List[str]:
        if typ.name == 'int':
            return [
                '    CPyTagged {};'.format(dest),
                '    if (PyLong_Check({}))'.format(src),
                '        {} = CPyTagged_FromObject({});'.format(dest, src),
                '    else',
                failure,
            ]
        elif typ.name == 'bool':
            return [
                '    if(!PyBool_Check({}))'.format(src),
                failure,
                '    char {} = PyObject_IsTrue({});'.format(dest, src)
            ]
        elif typ.name == 'list':
            return [
                '    PyObject *{};'.format(dest),
                '    if (PyList_Check({}))'.format(src),
                '        {} = {};'.format(dest, src),
                '    else',
                failure,
            ]
        elif typ.name == 'tuple':
            assert isinstance(typ, TupleRTType)
            self.declare_tuple_struct(typ)
            result = [
                '    if (!PyTuple_Check({}) || PyTuple_Size({}) != {})'.format(src, src, len(typ.types)),
                failure,
                '    {} {};'.format(typ.ctype, dest)
            ]
            for i in range(0, len(typ.types)):
                temp = self.temp_name()
                result.append('    PyObject *{} = PyTuple_GetItem({}, {});'.format(temp, src, i))

                temp2 = self.temp_name()
                # Unbox and check the sub-argument
                result += self.generate_unbox('{}'.format(temp), temp2,
                    typ.types[i], failure)

                result.append('    {}.f{} = {};'.format(dest, i, temp2))
            return result
        else:
            assert False, typ


    def generate_arg_check(self, name: str, typ: RTType) -> List[str]:
        """Insert a runtime check for argument and unbox if necessary.

        The object is named PyObject *obj_{}. This is expected to generate
        a value of name arg_{} (unboxed if necessary). For each primitive a runtime
        check ensures the correct type.
        """
        return self.generate_unbox('obj_{}'.format(name), 'arg_{}'.format(name), typ, '        return NULL;')



class Emitter:
    def __init__(self, code_generator: CodeGenerator, env: Environment) -> None:
        self.env = env
        self.declarations = []  # type: List[str]
        self.fragments = []  # type: List[str]
        self.code_generator = code_generator

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
        self.code_generator = self.emitter.code_generator
        self.env = self.emitter.env

    def temp_name(self) -> str:
        return self.code_generator.temp_name()

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
        neg = '!' if op.negated else ''

        if op.op == Branch.BOOL_EXPR:
            expr_result = self.reg(op.left) # right isn't used
            self.emit_line('if ({}({}))'.format(neg, expr_result))
        else:
            left = self.reg(op.left)
            right = self.reg(op.right)
            fn = EmitterVisitor.BRANCH_OP_MAP[op.op]
            self.emit_line('if (%s%s(%s, %s))' % (neg, fn, left, right))

        self.emit_lines(
            '    goto %s;' % self.label(op.true),
            'else',
            '    goto %s;' % self.label(op.false),
        )

    def visit_return(self, op: Return) -> None:
        typ = self.type(op.reg)
        assert typ.name in ('bool', 'int', 'list', 'tuple', 'None')
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
            self.emit_lines(
                '{} = Py_None;'.format(dest),
                'Py_INCREF({});'.format(dest),
            )

        elif op.desc is PrimitiveOp.TRUE:
            self.emit_line('{} = 1;'.format(dest))

        elif op.desc is PrimitiveOp.FALSE:
            self.emit_line('{} = 0;'.format(dest))

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

    def visit_tuple_get(self, op: TupleGet) -> None:
        dest = self.reg(op.dest)
        src = self.reg(op.src)
        self.emit_line('{} = {}.f{};'.format(dest, src, op.index))
        self._inc_ref(dest, op.target_type)

    def visit_call(self, op: Call) -> None:
        if op.dest is not None:
            dest = self.reg(op.dest) + ' = '
        else:
            dest = ''
        args = ', '.join(self.reg(arg) for arg in op.args)
        self.emit_line('%s%s%s(%s);' % (dest, NATIVE_PREFIX, op.fn, args))

    def visit_inc_ref(self, op: IncRef) -> None:
        dest = self.reg(op.dest)
        self._inc_ref(dest, op.target_type)

    def _inc_ref(self, dest: str, target_type: RTType) -> None:
        """Increment a reference to dest (which is confusingly an rvalue).

        For unpacked structures (e.g. tuples) recursively increment references inside.
        """
        if target_type.name == 'int':
            self.emit_line('CPyTagged_IncRef(%s);' % dest)
        elif isinstance(target_type, TupleRTType):
            i = 0
            for typ in target_type.types:
                self._inc_ref('{}.f{}'.format(dest, i), typ)
                i += 1
        else:
            if not target_type.supports_unbox:
                self.emit_line('Py_INCREF(%s);' % dest)

    def visit_dec_ref(self, op: DecRef) -> None:
        dest = self.reg(op.dest)
        self._dec_ref(dest, op.target_type)

    def _dec_ref(self, dest: str, target_type: RTType) -> None:
        """Decrement a reference to dest (which is confusingly an rvalue).

        For unpacked structures (e.g. tuples) recursively decrement references inside.
        """
        if target_type.name == 'int':
            self.emit_line('CPyTagged_DecRef(%s);' % dest)
        elif isinstance(target_type, TupleRTType):
            i = 0
            for typ in target_type.types:
                self._dec_ref('{}.f{}'.format(dest, i), typ)
                i += 1
        else:
            if not target_type.supports_unbox:
                self.emit_line('Py_DECREF(%s);' % dest)

    def visit_box(self, op: Box) -> None:
        # dest is already declared but generate_box will declare, so indirection is needed.
        src = self.reg(op.src)
        dest = self.reg(op.dest)
        temp = self.temp_name()
        self.emit_lines(*self.code_generator.generate_box(src, temp, op.type, 'abort();'))
        self.emit_line('{} = {};'.format(dest, temp))

    def visit_unbox(self, op: Unbox) -> None:
        # dest is already declared but generate_unbox will declare, so indirection is needed.
        src = self.reg(op.src)
        dest = self.reg(op.dest)
        temp = self.temp_name()
        self.emit_lines(*self.code_generator.generate_unbox(src, temp, op.type, 'abort();'))
        self.emit_line('{} = {};'.format(dest, temp))

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


def native_function_header(fn: FuncIR) -> str:
    args = []
    for arg in fn.args:
        args.append('{}{}{}'.format(arg.type.ctype_spaced, REG_PREFIX, arg.name))

    return 'static {ret_type} {prefix}{name}({args})'.format(
        ret_type=fn.ret_type.ctype,
        prefix=NATIVE_PREFIX,
        name=fn.name,
        args=', '.join(args) or 'void')


def wrapper_function_header(fn: FuncIR) -> str:
    return 'static PyObject *{prefix}{name}(PyObject *self, PyObject *args, PyObject *kw)'.format(
            prefix=PREFIX,
            name=fn.name)
