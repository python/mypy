import textwrap
from typing import List, Set, Dict

from mypyc.common import PREFIX, NATIVE_PREFIX, REG_PREFIX
from mypyc.ops import (
    OpVisitor, Environment, Label, Register, RTType, FuncIR, Goto, Branch, Return, PrimitiveOp,
    Assign, LoadInt, IncRef, DecRef, Call, Box, Unbox, TupleRTType, TupleGet, UserRTType, ClassIR,
    GetAttr, SetAttr, PyCall, LoadStatic, PyGetAttr, Cast, OP_BINARY, type_struct_name,
    c_module_name
)


class Emitter:
    """Helper for C code generation."""

    def __init__(self, env: Environment = None) -> None:
        self.env = env or Environment()
        self.fragments = []  # type: List[str]
        self._indent = 0

    def indent(self) -> None:
        self._indent += 4

    def dedent(self) -> None:
        self._indent -= 4
        assert self._indent >= 0

    def label(self, label: Label) -> str:
        return 'CPyL%d' % label

    def reg(self, reg: Register) -> str:
        name = self.env.names[reg]
        return REG_PREFIX + name

    def emit_line(self, line: str = '') -> None:
        if line.startswith('}'):
            self.dedent()
        self.fragments.append(self._indent * ' ' + line + '\n')
        if line.endswith('{'):
            self.indent()

    def emit_lines(self, *lines: str) -> None:
        for line in lines:
            self.emit_line(line)

    def emit_label(self, label: Label) -> None:
        # Extra semicolon prevents an error when the next line declares a tempvar
        self.fragments.append('{}: ;\n'.format(self.label(label)))

    def emit_from_emitter(self, emitter: 'Emitter') -> None:
        self.fragments.extend(emitter.fragments)


class HeaderDeclaration:
    def __init__(self, dependencies: Set[str], body: List[str]) -> None:
        self.dependencies = dependencies
        self.body = body


class MarkedDeclaration:
    """Add a mark, useful for topological sort."""
    def __init__(self, declaration: HeaderDeclaration, mark: bool) -> None:
        self.declaration = declaration
        self.mark = False


def getter_name(cl: str, attribute: str) -> str:
    return '{}_get{}'.format(cl, attribute)


def setter_name(cl: str, attribute: str) -> str:
    return '{}_set{}'.format(cl, attribute)


def native_getter_name(cl: str, attribute: str) -> str:
    return 'native_{}_get{}'.format(cl, attribute)


def native_setter_name(cl: str, attribute: str) -> str:
    return 'native_{}_set{}'.format(cl, attribute)


class CodeGenerator:
    def __init__(self) -> None:
        self.temp_counter = 0

        # A map of a C identifier to whatever the C identifier declares. Currently this is
        # used for declaring structsm and the key corresponds to the name of the struct.
        # The declaration contains the body of the struct.
        self.declarations = {} # type: Dict[str, HeaderDeclaration]

    def toposort_declarations(self) -> List[HeaderDeclaration]:
        """Topologically sort the declaration dict by dependencies.

        Declarations can require other declarations to come prior in C (such as declaring structs).
        In order to guarantee that the C output will compile the declarations will thus need to
        be properly ordered. This simple DFS guarantees that we have a proper ordering.

        This runs in O(V + E).
        """
        result = []
        marked_declarations = {k: MarkedDeclaration(v, False)
                               for k, v in self.declarations.items()}

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

    def declare_global(self, type_spaced, name, static=True) -> None:
        static_str = 'static ' if static else ''
        if name not in self.declarations:
            self.declarations[name] = HeaderDeclaration(
                set(),
                ['{}{}{};'.format(static_str, type_spaced, name)],
            )

    def declare_import(self, imp: str) -> None:
        self.declare_global('CPyModule *', c_module_name(imp))

    def declare_imports(self, imps) -> None:
        for imp in imps:
            self.declare_import(imp)

    def temp_name(self) -> str:
        self.temp_counter += 1
        return '__tmp%d' % self.temp_counter

    def generate_imports_init_section(self, imps: List[str], emitter: Emitter) -> None:
        for imp in imps:
            emitter.emit_line('/* import {} */'.format(imp))
            emitter.emit_line('{} = PyImport_ImportModule("{}");'.format(c_module_name(imp), imp))
            emitter.emit_line('if ({} == NULL)'.format(c_module_name(imp)))
            emitter.emit_line('    return NULL;')

    def generate_c_for_function(self, fn: FuncIR, emitter: Emitter) -> None:
        declarations = Emitter(fn.env)
        body = Emitter(fn.env)
        visitor = EmitterVisitor(body, declarations, self)

        declarations.emit_line('{} {{'.format(native_function_header(fn)))
        body.indent()

        for i in range(len(fn.args), fn.env.num_regs()):
            ctype = fn.env.types[i].ctype
            declarations.emit_line('{ctype} {prefix}{name};'.format(ctype=ctype,
                                                                    prefix=REG_PREFIX,
                                                                    name=fn.env.names[i]))

        for block in fn.blocks:
            body.emit_label(block.label)
            for op in block.ops:
                op.accept(visitor)

        body.emit_line('}')

        emitter.emit_from_emitter(declarations)
        emitter.emit_from_emitter(body)

    def generate_box(self, src: str, dest: str, typ: RTType, failure: str) -> List[str]:
        """Generate code for boxing a value of give type.

        Generate a simple assignment if no boxing is needed.
        """
        if typ.name == 'int':
            return ['PyObject *{} = CPyTagged_AsObject({});'.format(dest, src)]
        elif typ.name == 'bool':
            # The Py_RETURN macros return the correct PyObject * with reference count handling.
            return ['PyObject *{} = PyBool_FromLong({});'.format(dest, src)]
        elif typ.name == 'tuple':
            assert isinstance(typ, TupleRTType)
            self.declare_tuple_struct(typ)
            result = []
            result.append('PyObject *{} = PyTuple_New({});'.format(dest, len(typ.types)))
            result.append('if ({} == NULL) {{'.format(dest))
            result.append('    {}'.format(failure))
            result.append('}')
            # TODO: Fail if dest is None
            for i in range(0, len(typ.types)):
                if not typ.supports_unbox:
                    result.append('PyTuple_SetItem({}, {}, {}.f{}'.format(dest, i, src, i))
                else:
                    inner_name = self.temp_name()
                    result += self.generate_box('{}.f{}'.format(src, i), inner_name, typ.types[i],
                                                failure)
                    result.append('PyTuple_SetItem({}, {}, {});'.format(dest, i, inner_name, i))
            return result
        else:
            # Type is boxed -- trivially just assign.
            return ['PyObject *{} = {};'.format(dest, src)]

    def generate_wrapper_function(self, fn: FuncIR, emitter: Emitter) -> None:
        """Generates a CPython-compatible wrapper function for a native function.

        In particular, this handles unboxing the arguments, calling the native function, and
        then boxing the return value.
        """
        emitter.emit_line('{} {{'.format(wrapper_function_header(fn)))
        arg_names = ''.join('"{}", '.format(arg.name) for arg in fn.args)
        emitter.emit_line('static char *kwlist[] = {{{}0}};'.format(arg_names))
        for arg in fn.args:
            emitter.emit_line('PyObject *obj_{};'.format(arg.name))
        arg_spec = 'O' * len(fn.args)
        arg_ptrs = ''.join(', &obj_{}'.format(arg.name) for arg in fn.args)
        emitter.emit_lines(
            'if (!PyArg_ParseTupleAndKeywords(args, kw, "{}:f", kwlist{})) {{'.format(
                arg_spec, arg_ptrs),
            'return NULL;',
            '}')
        for arg in fn.args:
            check = self.generate_arg_check(arg.name, arg.type)
            emitter.emit_lines(*check)
        native_args = ', '.join('arg_{}'.format(arg.name) for arg in fn.args)

        if fn.ret_type.supports_unbox:
            if fn.ret_type.name == 'int':
                emitter.emit_lines('CPyTagged retval = CPyDef_{}({});'.format(fn.name, native_args),
                                   'if (retval == CPY_INT_ERROR_VALUE && PyErr_Occurred()) {',
                                   'return NULL; // TODO: Add traceback entry?',
                                   '}')
                box = self.generate_box('retval', 'retbox', fn.ret_type, 'return NULL;')
                emitter.emit_lines(*box)
                # TODO: Decrease reference count of retval?
                emitter.emit_lines('return retbox;')
            elif fn.ret_type.name == 'bool':
                # The Py_RETURN macros return the correct PyObject * with reference count handling.
                emitter.emit_line('char retval = {}{}({});'.format(NATIVE_PREFIX, fn.name,
                                                                   native_args))
                box = self.generate_box('retval', 'retbox', fn.ret_type, 'return NULL;')
                emitter.emit_lines(*box)
                emitter.emit_line('return retbox;')
            elif fn.ret_type.name == 'tuple':
                emitter.emit_line('{}retval = {}{}({});'.format(fn.ret_type.ctype_spaced,
                                                                NATIVE_PREFIX, fn.name,
                                                                native_args))
                box = self.generate_box('retval', 'retbox', fn.ret_type, 'return NULL;')
                emitter.emit_lines(*box)
                emitter.emit_line('return retbox;')
        else:
            # Any type that needs to be unboxed should be special cased, so fail if
            # we failed to do so.
            assert not fn.ret_type.supports_unbox
            emitter.emit_line(' return CPyDef_{}({});'.format(fn.name, native_args))
            # TODO: Tracebacks?
        emitter.emit_line('}')

    def generate_unbox(self, src: str, dest: str, typ: RTType, failure: str) -> List[str]:
        failure = '    ' + failure
        if typ.name == 'int':
            return [
                'CPyTagged {};'.format(dest),
                'if (PyLong_Check({}))'.format(src),
                '    {} = CPyTagged_FromObject({});'.format(dest, src),
                'else',
                failure,
            ]
        elif typ.name == 'bool':
            return [
                'if (!PyBool_Check({}))'.format(src),
                failure,
                'char {} = PyObject_IsTrue({});'.format(dest, src)
            ]
        elif typ.name == 'list':
            return [
                'PyObject *{};'.format(dest),
                'if (PyList_Check({}))'.format(src),
                '    {} = {};'.format(dest, src),
                'else',
                failure,
            ]
        elif typ.name == 'sequence_tuple':
            return [
                'if (!PyTuple_Check({}))'.format(src),
                failure,
                '{} {} = {};'.format(typ.ctype, dest, src)
            ]
        elif typ.name == 'tuple':
            assert isinstance(typ, TupleRTType)
            self.declare_tuple_struct(typ)
            result = [
                'if (!PyTuple_Check({}) || PyTuple_Size({}) != {})'.format(src, src,
                                                                           len(typ.types)),
                failure,
                '{} {};'.format(typ.ctype, dest)
            ]
            for i in range(0, len(typ.types)):
                temp = self.temp_name()
                result.append('PyObject *{} = PyTuple_GetItem({}, {});'.format(temp, src, i))

                temp2 = self.temp_name()
                # Unbox and check the sub-argument
                result += self.generate_unbox('{}'.format(temp), temp2,
                    typ.types[i], failure)

                result.append('{}.f{} = {};'.format(dest, i, temp2))
            return result
        elif isinstance(typ, UserRTType):
            return [
                'PyObject *{};'.format(dest),
                'if (PyObject_TypeCheck({}, &{}))'.format(src, type_struct_name(typ.name)),
                '    {} = {};'.format(dest, src),
                'else',
                failure
            ]
        assert False, 'Unboxing not implemented: %s' % typ

    def generate_arg_check(self, name: str, typ: RTType) -> List[str]:
        """Insert a runtime check for argument and unbox if necessary.

        The object is named PyObject *obj_{}. This is expected to generate
        a value of name arg_{} (unboxed if necessary). For each primitive a runtime
        check ensures the correct type.
        """
        return self.generate_unbox('obj_{}'.format(name), 'arg_{}'.format(name), typ,
                                   'return NULL;')

    def generate_inc_ref(self, dest: str, rtype: RTType) -> List[str]:
        """Increment reference count of C expression `dest`.

        For composite unboxed structures (e.g. tuples) recursively
        increment reference counts for each component.
        """
        if rtype.name == 'int':
            return ['CPyTagged_IncRef(%s);' % dest]
        elif isinstance(rtype, TupleRTType):
            result = []
            for i, item_type in enumerate(rtype.types):
                result.extend(self.generate_inc_ref('{}.f{}'.format(dest, i), item_type))
            return result
        elif not rtype.supports_unbox:
            return ['Py_INCREF(%s);' % dest]
        # Otherwise assume it's an unboxed, pointerless value.
        return []

    def generate_dec_ref(self, dest: str, rtype: RTType) -> List[str]:
        """Decrement reference count of C expression `dest`.

        For composite unboxed structures (e.g. tuples) recursively
        decrement reference counts for each component.
        """
        if rtype.name == 'int':
            return ['CPyTagged_DecRef(%s);' % dest]
        elif isinstance(rtype, TupleRTType):
            result = []
            for i, item_type in enumerate(rtype.types):
                result.extend(self.generate_dec_ref('{}.f{}'.format(dest, i), item_type))
            return result
        elif not rtype.supports_unbox:
            return ['Py_DECREF(%s);' % dest]
        # Otherwise assume it's an unboxed, pointerless value.
        return []

    def generate_class_declaration(self,
                                   cl: ClassIR,
                                   module: str) -> List[str]:
        name = cl.name
        fullname = '{}.{}'.format(module, name)
        new_name = '{}_new'.format(name)
        dealloc_name = '{}_dealloc'.format(name)
        getseters_name = '{}_getseters'.format(name)
        vtable_name = '{}_vtable'.format(name)

        result = []  # type: List[str]
        # Use dummy empty __init__ for now.
        init = FuncIR(cl.name, [], RTType(cl.name), [], Environment())
        result.append(native_function_header(init) + ';')
        result.extend(self.generate_object_struct(cl))
        result.append('')
        result.extend(self.generate_new_for_class(cl, new_name, vtable_name))
        result.append('')
        result.extend(self.generate_dealloc_for_class(cl, dealloc_name))
        result.append('')
        result.extend(self.generate_native_getters_and_setters(cl))
        result.extend(self.generate_vtable(cl, vtable_name))
        result.append('')
        result.extend(self.generate_getseter_declarations(cl))
        result.extend(self.generate_getseters_table(cl, getseters_name))
        result.append('')

        result.append(textwrap.dedent("""\
            static PyTypeObject {type_struct} = {{
                PyVarObject_HEAD_INIT(NULL, 0)
                "{fullname}",              /* tp_name */
                sizeof({struct_name}),     /* tp_basicsize */
                0,                         /* tp_itemsize */
                (destructor){dealloc_name},  /* tp_dealloc */
                0,                         /* tp_print */
                0,                         /* tp_getattr */
                0,                         /* tp_setattr */
                0,                         /* tp_reserved */
                0,                         /* tp_repr */
                0,                         /* tp_as_number */
                0,                         /* tp_as_sequence */
                0,                         /* tp_as_mapping */
                0,                         /* tp_hash  */
                0,                         /* tp_call */
                0,                         /* tp_str */
                0,                         /* tp_getattro */
                0,                         /* tp_setattro */
                0,                         /* tp_as_buffer */
                Py_TPFLAGS_DEFAULT,        /* tp_flags */
                0,                         /* tp_doc */
                0,                         /* tp_traverse */
                0,                         /* tp_clear */
                0,                         /* tp_richcompare */
                0,                         /* tp_weaklistoffset */
                0,                         /* tp_iter */
                0,                         /* tp_iternext */
                0,                         /* tp_methods */
                0,                         /* tp_members */
                {getseters_name},          /* tp_getset */
                0,                         /* tp_base */
                0,                         /* tp_dict */
                0,                         /* tp_descr_get */
                0,                         /* tp_descr_set */
                0,                         /* tp_dictoffset */
                0,                         /* tp_init */
                0,                         /* tp_alloc */
                {new_name},                /* tp_new */
            }};\
            """).format(type_struct=type_struct_name(cl.name),
                        struct_name=cl.struct_name,
                        fullname=fullname,
                        dealloc_name=dealloc_name,
                        new_name=new_name,
                        getseters_name=getseters_name))
        result.append('')
        result.extend(self.generate_constructor_for_class(cl, new_name, vtable_name))
        result.extend(self.generate_getseters(cl))
        return result

    def generate_object_struct(self, cl: ClassIR) -> List[str]:
        result = []
        result.append('typedef struct {')
        result.append('    PyObject_HEAD')
        result.append('    CPyVTableItem *vtable;')
        for attr, rtype in cl.attributes:
            result.append('    {}{};'.format(rtype.ctype_spaced, attr))
        result.append('}} {};'.format(cl.struct_name))
        return result

    def generate_native_getters_and_setters(self,
                                            cl: ClassIR) -> List[str]:
        result = []
        for attr, rtype in cl.attributes:
            result.append('{}{}({} *self)'.format(rtype.ctype_spaced,
                                                   native_getter_name(cl.name, attr),
                                                   cl.struct_name))
            result.append('{')
            result.append('    if (self->{} != {}) {{'.format(attr, rtype.c_undefined_value))
            result.extend(self.generate_inc_ref('self->{}'.format(attr), rtype))
            result.append('    }')
            result.append('    return self->{};'.format(attr))
            result.append('}')
            result.append('')
            result.append('void {}({} *self, {}value)'.format(native_setter_name(cl.name, attr),
                                                              cl.struct_name,
                                                              rtype.ctype_spaced))
            result.append('{')
            result.append('    if (self->{} != {}) {{'.format(attr, rtype.c_undefined_value))
            result.extend(self.generate_dec_ref('self->{}'.format(attr), rtype))
            result.append('    }')
            result.extend(self.generate_inc_ref('value'.format(attr), rtype))
            result.append('    self->{} = value;'.format(attr))
            result.append('}')
            result.append('')
        return result

    def generate_vtable(self,
                        cl: ClassIR,
                        vtable_name: str) -> List[str]:
        result = []
        result.append('static CPyVTableItem {}[] = {{'.format(vtable_name))
        for attr, rtype in cl.attributes:
            result.append('    (CPyVTableItem){},'.format(native_getter_name(cl.name, attr)))
            result.append('    (CPyVTableItem){},'.format(native_setter_name(cl.name, attr)))
        result.append('};')
        return result

    def generate_constructor_for_class(self, cl: ClassIR, func_name: str,
                                       vtable_name: str) -> List[str]:
        """Generate a native function that constructs an instance of a class."""
        result = []
        result.append('static PyObject *')
        result.append('CPyDef_{}(void)'.format(cl.name))
        result.append('{')
        result.append('    {} *self;'.format(cl.struct_name))
        result.append('    self = ({} *){}.tp_alloc(&{}, 0);'.format(cl.struct_name,
                                                                     cl.type_struct,
                                                                     cl.type_struct))
        result.append('    if (self == NULL)')
        result.append('        abort(); // TODO')
        result.append('    self->vtable = {};'.format(vtable_name))
        for attr, rtype in cl.attributes:
            result.append('    self->{} = {};'.format(attr, rtype.c_undefined_value))
        result.append('    return (PyObject *)self;')
        result.append('}')
        return result

    def generate_new_for_class(self, cl: ClassIR, func_name: str, vtable_name: str) -> List[str]:
        result = []
        result.append('static PyObject *')
        result.append('{}(PyTypeObject *type, PyObject *args, PyObject *kwds)'.format(func_name))
        result.append('{')
        # TODO: Check and unbox arguments
        result.append('    return CPyDef_{}();'.format(cl.name))
        result.append('}')
        return result

    def generate_dealloc_for_class(self, cl: ClassIR, func_name: str) -> List[str]:
        result = []
        result.append('static void')
        result.append('{}({} *self)'.format(func_name, cl.struct_name))
        result.append('{')
        for attr, rtype in cl.attributes:
            result.append('    if (self->{} != {}) {{'.format(attr, rtype.c_undefined_value))
            result.extend(self.generate_dec_ref('self->{}'.format(attr), rtype))
            result.append('    }')
        result.append('    Py_TYPE(self)->tp_free((PyObject *)self);')
        result.append('}')
        return result

    def generate_getseter_declarations(self, cl: ClassIR) -> List[str]:
        result = []
        for attr, rtype in cl.attributes:
            result.append('static PyObject *')
            result.append('{}({} *self, void *closure);'.format(getter_name(cl.name, attr),
                                                                cl.struct_name))
            result.append('static int')
            result.append('{}({} *self, PyObject *value, void *closure);'.format(
                setter_name(cl.name, attr),
                cl.struct_name))
        return result

    def generate_getseters_table(self,
                                 cl: ClassIR,
                                 name: str) -> List[str]:

        result = []
        result.append('static PyGetSetDef {}[] = {{'.format(name))
        for attr, rtype in cl.attributes:
            result.append('    {{"{}",'.format(attr))
            result.append('     (getter){}, (setter){},'.format(getter_name(cl.name, attr),
                                                                setter_name(cl.name, attr)))
            result.append('     NULL, NULL},')
        result.append('    {NULL}  /* Sentinel */')
        result.append('};')
        return result

    def generate_getseters(self, cl: ClassIR) -> List[str]:
        result = []  # type: List[str]
        for attr, rtype in cl.attributes:
            result.extend(self.generate_getter(cl, attr, rtype))
            result.append('')
            result.extend(self.generate_setter(cl, attr, rtype))
            result.append('')
        return result

    def generate_getter(self,
                        cl: ClassIR,
                        attr: str,
                        rtype: RTType) -> List[str]:
        result = []
        result.append('static PyObject *')
        result.append('{}({} *self, void *closure)'.format(getter_name(cl.name, attr),
                                                                            cl.struct_name))
        result.append('{')
        result.append('    if (self->{} == {}) {{'.format(attr, rtype.c_undefined_value))
        result.append('        PyErr_SetString(PyExc_AttributeError,')
        result.append('            "attribute {} of {} undefined");'.format(repr(attr),
                                                                            repr(cl.name)))
        result.append('        return NULL;')
        result.append('    }')
        result.extend(self.generate_box('self->{}'.format(attr),
                                        'retval', rtype, 'abort();'))
        result.append('    return retval;')
        result.append('}')
        return result

    def generate_setter(self,
                        cl: ClassIR,
                        attr: str,
                        rtype: RTType) -> List[str]:
        result = []
        result.append('static int')
        result.append('{}({} *self, PyObject *value, void *closure)'.format(
            setter_name(cl.name, attr),
            cl.struct_name))
        result.append('{')
        result.append('    if (self->{} != {}) {{'.format(attr, rtype.c_undefined_value))
        result.extend(self.generate_dec_ref('self->{}'.format(attr), rtype))
        result.append('    }')
        result.append('    if (value != NULL) {')
        result.extend(self.generate_unbox('value', 'tmp', rtype, 'abort();'))
        result.append('        self->{} = tmp;'.format(attr))
        result.append('    } else')
        result.append('        self->{} = {};'.format(attr, rtype.c_undefined_value))
        result.append('    return 0;')
        result.append('}')
        return result


class EmitterVisitor(OpVisitor):
    def __init__(self, emitter: Emitter, declarations: Emitter,
                 code_generator: CodeGenerator) -> None:
        self.emitter = emitter
        self.declarations = declarations
        self.code_generator = code_generator
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
        assert typ.name != 'object'
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
                self.declarations.emit_line('long long %s;' % temp)
                self.emit_lines(
                    '%s = CPyTagged_AsLongLong(%s);' % (temp, right),
                    'if (%s == -1 && PyErr_Occurred())' % temp,
                    '    abort();',
                    '%s = PySequence_Repeat(%s, %s);' % (dest, left, temp),
                    'if (!%s)' % dest,
                    '    abort();')
            elif op.desc is PrimitiveOp.HOMOGENOUS_TUPLE_GET:
                self.emit_lines('%s = CPySequenceTuple_GetItem(%s, %s);' % (dest, left, right),
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

        elif op.desc is PrimitiveOp.NEW_TUPLE:
            tuple_type = self.env.types[op.dest]
            assert isinstance(tuple_type, TupleRTType)
            self.code_generator.declare_tuple_struct(tuple_type)
            for i, arg in enumerate(op.args):
                self.emit_line('{}.f{} = {};'.format(dest, i, self.reg(arg)))
            self.emit_inc_ref(dest, tuple_type)

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
                self.declarations.emit_line('long long %s;' % temp)
                self.emit_line('%s = PyList_GET_SIZE(%s);' % (temp, src))
                self.emit_line('%s = CPyTagged_ShortFromLongLong(%s);' % (dest, temp))
            elif op.desc is PrimitiveOp.HOMOGENOUS_TUPLE_LEN:
                temp = self.temp_name()
                self.declarations.emit_line('long long %s;' % temp)
                self.emit_line('%s = PyTuple_GET_SIZE(%s);' % (temp, src))
                self.emit_line('%s = CPyTagged_ShortFromLongLong(%s);' % (dest, temp))
            elif op.desc is PrimitiveOp.LIST_TO_HOMOGENOUS_TUPLE:
                self.emit_line('%s = PyList_AsTuple(%s);' % (dest, src))
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

    def visit_get_attr(self, op: GetAttr) -> None:
        dest = self.reg(op.dest)
        obj = self.reg(op.obj)
        rtype = op.rtype
        self.emit_line('%s = CPY_GET_ATTR(%s, %d, %s, %s);' % (
            dest, obj,
            rtype.getter_index(op.attr),
            rtype.struct_name,
            rtype.attr_type(op.attr).ctype))

    def visit_set_attr(self, op: SetAttr) -> None:
        obj = self.reg(op.obj)
        src = self.reg(op.src)
        rtype = op.rtype
        self.emit_line('CPY_SET_ATTR(%s, %d, %s, %s, %s);' % (
            obj,
            rtype.setter_index(op.attr),
            src,
            rtype.struct_name,
            rtype.attr_type(op.attr).ctype))

    def visit_load_static(self, op: LoadStatic) -> None:
        dest = self.reg(op.dest)
        self.emit_line('%s = %s;' % (dest, op.identifier))

    def visit_py_get_attr(self, op: PyGetAttr) -> None:
        dest = self.reg(op.dest)
        left = self.reg(op.left)
        self.emit_line('{} = CPyObject_GetAttrString({}, "{}");'.format(dest, left, op.right))

    def visit_tuple_get(self, op: TupleGet) -> None:
        dest = self.reg(op.dest)
        src = self.reg(op.src)
        self.emit_line('{} = {}.f{};'.format(dest, src, op.index))
        self.emit_inc_ref(dest, op.target_type)

    def visit_call(self, op: Call) -> None:
        if op.dest is not None:
            dest = self.reg(op.dest) + ' = '
        else:
            dest = ''
        args = ', '.join(self.reg(arg) for arg in op.args)
        self.emit_line('%s%s%s(%s);' % (dest, NATIVE_PREFIX, op.fn, args))

    def visit_py_call(self, op: PyCall) -> None:
        if op.dest is not None:
            dest = self.reg(op.dest) + ' = '
        else:
            dest = ''

        function = self.reg(op.function)
        args = ', '.join(self.reg(arg) for arg in op.args)
        self.emit_line('{}PyObject_CallFunctionObjArgs({}, {}, NULL);'.format(dest, function, args))

    def visit_inc_ref(self, op: IncRef) -> None:
        dest = self.reg(op.dest)
        self.emit_inc_ref(dest, op.target_type)

    def visit_dec_ref(self, op: DecRef) -> None:
        dest = self.reg(op.dest)
        self.emit_dec_ref(dest, op.target_type)

    def visit_box(self, op: Box) -> None:
        # dest is already declared but generate_box will declare, so indirection is needed.
        src = self.reg(op.src)
        dest = self.reg(op.dest)
        temp = self.temp_name()
        self.emit_lines(*self.code_generator.generate_box(src, temp, op.type, 'abort();'))
        self.emit_line('{} = {};'.format(dest, temp))

    def visit_cast(self, op: Cast) -> None:
        # TODO Actually cast things (runtime check). (#43)
        src = self.reg(op.src)
        dest = self.reg(op.dest)
        self.emit_line('{} = {};'.format(dest, src))

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

    def emit_line(self, line: str) -> None:
        self.emitter.emit_line(line)

    def emit_lines(self, *lines: str) -> None:
        self.emitter.emit_lines(*lines)

    def emit_print(self, args: str) -> None:
        """Emit printf call (for debugging mypyc)."""
        self.emit_line(r'printf(%s);' % args)
        self.emit_line(r'printf("\n");')
        self.emit_line(r'fflush(stdout);')

    def emit_inc_ref(self, dest: str, rtype: RTType) -> None:
        lines = self.code_generator.generate_inc_ref(dest, rtype)
        self.emit_lines(*lines)

    def emit_dec_ref(self, dest: str, rtype: RTType) -> None:
        lines = self.code_generator.generate_dec_ref(dest, rtype)
        self.emit_lines(*lines)


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
