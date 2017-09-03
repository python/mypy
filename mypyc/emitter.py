import textwrap
from typing import List, Dict

from mypyc.common import PREFIX, NATIVE_PREFIX
from mypyc.emitcommon import Emitter, HeaderDeclaration, EmitterContext
from mypyc.emitfunc import native_function_header
from mypyc.ops import Environment, RTType, FuncIR,  ClassIR, type_struct_name, c_module_name


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
    def __init__(self, context: EmitterContext) -> None:
        self.context = context

    def toposort_declarations(self) -> List[HeaderDeclaration]:
        """Topologically sort the declaration dict by dependencies.

        Declarations can require other declarations to come prior in C (such as declaring structs).
        In order to guarantee that the C output will compile the declarations will thus need to
        be properly ordered. This simple DFS guarantees that we have a proper ordering.

        This runs in O(V + E).
        """
        result = []
        marked_declarations = {k: MarkedDeclaration(v, False)
                               for k, v in self.context.declarations.items()}

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

    def declare_global(self, type_spaced, name, static=True) -> None:
        static_str = 'static ' if static else ''
        if name not in self.context.declarations:
            self.context.declarations[name] = HeaderDeclaration(
                set(),
                ['{}{}{};'.format(static_str, type_spaced, name)],
            )

    def declare_import(self, imp: str) -> None:
        self.declare_global('CPyModule *', c_module_name(imp))

    def declare_imports(self, imps) -> None:
        for imp in imps:
            self.declare_import(imp)

    def generate_imports_init_section(self, imps: List[str], emitter: Emitter) -> None:
        for imp in imps:
            emitter.emit_line('/* import {} */'.format(imp))
            emitter.emit_line('{} = PyImport_ImportModule("{}");'.format(c_module_name(imp), imp))
            emitter.emit_line('if ({} == NULL)'.format(c_module_name(imp)))
            emitter.emit_line('    return NULL;')

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
            self.generate_arg_check(arg.name, arg.type, emitter)
        native_args = ', '.join('arg_{}'.format(arg.name) for arg in fn.args)

        if fn.ret_type.supports_unbox:
            if fn.ret_type.name == 'int':
                emitter.emit_lines('CPyTagged retval = CPyDef_{}({});'.format(fn.name, native_args),
                                   'if (retval == CPY_INT_ERROR_VALUE && PyErr_Occurred()) {',
                                   'return NULL; // TODO: Add traceback entry?',
                                   '}')
                emitter.emit_box('retval', 'retbox', fn.ret_type, 'return NULL;')
                # TODO: Decrease reference count of retval?
                emitter.emit_lines('return retbox;')
            elif fn.ret_type.name == 'bool':
                # The Py_RETURN macros return the correct PyObject * with reference count handling.
                emitter.emit_line('char retval = {}{}({});'.format(NATIVE_PREFIX, fn.name,
                                                                   native_args))
                emitter.emit_box('retval', 'retbox', fn.ret_type, 'return NULL;')
                emitter.emit_line('return retbox;')
            elif fn.ret_type.name == 'tuple':
                emitter.emit_line('{}retval = {}{}({});'.format(fn.ret_type.ctype_spaced,
                                                                NATIVE_PREFIX, fn.name,
                                                                native_args))
                emitter.emit_box('retval', 'retbox', fn.ret_type, 'return NULL;')
                emitter.emit_line('return retbox;')
        else:
            # Any type that needs to be unboxed should be special cased, so fail if
            # we failed to do so.
            assert not fn.ret_type.supports_unbox
            emitter.emit_line(' return CPyDef_{}({});'.format(fn.name, native_args))
            # TODO: Tracebacks?
        emitter.emit_line('}')

    def generate_arg_check(self, name: str, typ: RTType, emitter: Emitter) -> None:
        """Insert a runtime check for argument and unbox if necessary.

        The object is named PyObject *obj_{}. This is expected to generate
        a value of name arg_{} (unboxed if necessary). For each primitive a runtime
        check ensures the correct type.
        """
        emitter.emit_unbox_or_cast('obj_{}'.format(name), 'arg_{}'.format(name), typ,
                                   'return NULL;')

    def generate_class(self, cl: ClassIR, module: str, emitter: Emitter) -> None:
        name = cl.name
        fullname = '{}.{}'.format(module, name)
        new_name = '{}_new'.format(name)
        dealloc_name = '{}_dealloc'.format(name)
        getseters_name = '{}_getseters'.format(name)
        vtable_name = '{}_vtable'.format(name)

        # Use dummy empty __init__ for now.
        init = FuncIR(cl.name, [], RTType(cl.name), [], Environment())
        emitter.emit_line(native_function_header(init) + ';')
        self.generate_object_struct(cl, emitter)
        emitter.emit_line()
        self.generate_new_for_class(cl, new_name, vtable_name, emitter)
        emitter.emit_line()
        self.generate_dealloc_for_class(cl, dealloc_name, emitter)
        emitter.emit_line()
        self.generate_native_getters_and_setters(cl, emitter)
        self.generate_vtable(cl, vtable_name, emitter)
        emitter.emit_line()
        self.generate_getseter_declarations(cl, emitter)
        self.generate_getseters_table(cl, getseters_name, emitter)
        emitter.emit_line()

        emitter.emit_line(textwrap.dedent("""\
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
        emitter.emit_line()
        self.generate_constructor_for_class(cl, new_name, vtable_name, emitter)
        self.generate_getseters(cl, emitter)

    def generate_object_struct(self, cl: ClassIR, emitter: Emitter) -> None:
        emitter.emit_lines('typedef struct {',
                           'PyObject_HEAD',
                           'CPyVTableItem *vtable;')
        for attr, rtype in cl.attributes:
            emitter.emit_line('{}{};'.format(rtype.ctype_spaced, attr))
        emitter.emit_line('}} {};'.format(cl.struct_name))

    def generate_native_getters_and_setters(self,
                                            cl: ClassIR,
                                            emitter: Emitter) -> None:
        for attr, rtype in cl.attributes:
            emitter.emit_line('{}{}({} *self)'.format(rtype.ctype_spaced,
                                                   native_getter_name(cl.name, attr),
                                                   cl.struct_name))
            emitter.emit_line('{')
            emitter.emit_line('if (self->{} != {}) {{'.format(attr, rtype.c_undefined_value))
            emitter.emit_inc_ref('self->{}'.format(attr), rtype)
            emitter.emit_line('}')
            emitter.emit_line('return self->{};'.format(attr))
            emitter.emit_line('}')
            emitter.emit_line()
            emitter.emit_line('void {}({} *self, {}value)'.format(native_setter_name(cl.name, attr),
                                                              cl.struct_name,
                                                              rtype.ctype_spaced))
            emitter.emit_line('{')
            emitter.emit_line('if (self->{} != {}) {{'.format(attr, rtype.c_undefined_value))
            emitter.emit_dec_ref('self->{}'.format(attr), rtype)
            emitter.emit_line('}')
            emitter.emit_inc_ref('value'.format(attr), rtype)
            emitter.emit_line('self->{} = value;'.format(attr))
            emitter.emit_line('}')
            emitter.emit_line()

    def generate_vtable(self,
                        cl: ClassIR,
                        vtable_name: str,
                        emitter: Emitter) -> None:
        emitter.emit_line('static CPyVTableItem {}[] = {{'.format(vtable_name))
        for attr, rtype in cl.attributes:
            emitter.emit_line('(CPyVTableItem){},'.format(native_getter_name(cl.name, attr)))
            emitter.emit_line('(CPyVTableItem){},'.format(native_setter_name(cl.name, attr)))
        emitter.emit_line('};')

    def generate_constructor_for_class(self,
                                       cl: ClassIR,
                                       func_name: str,
                                       vtable_name: str,
                                       emitter: Emitter) -> None:
        """Generate a native function that constructs an instance of a class."""
        emitter.emit_line('static PyObject *')
        emitter.emit_line('CPyDef_{}(void)'.format(cl.name))
        emitter.emit_line('{')
        emitter.emit_line('{} *self;'.format(cl.struct_name))
        emitter.emit_line('self = ({} *){}.tp_alloc(&{}, 0);'.format(cl.struct_name,
                                                                     cl.type_struct,
                                                                     cl.type_struct))
        emitter.emit_line('if (self == NULL)')
        emitter.emit_line('    abort(); // TODO')
        emitter.emit_line('self->vtable = {};'.format(vtable_name))
        for attr, rtype in cl.attributes:
            emitter.emit_line('self->{} = {};'.format(attr, rtype.c_undefined_value))
        emitter.emit_line('return (PyObject *)self;')
        emitter.emit_line('}')

    def generate_new_for_class(self,
                               cl: ClassIR,
                               func_name: str,
                               vtable_name: str,
                               emitter: Emitter) -> None:
        emitter.emit_line('static PyObject *')
        emitter.emit_line(
            '{}(PyTypeObject *type, PyObject *args, PyObject *kwds)'.format(func_name))
        emitter.emit_line('{')
        # TODO: Check and unbox arguments
        emitter.emit_line('return CPyDef_{}();'.format(cl.name))
        emitter.emit_line('}')

    def generate_dealloc_for_class(self,
                                   cl: ClassIR,
                                   func_name: str,
                                   emitter: Emitter) -> None:
        emitter.emit_line('static void')
        emitter.emit_line('{}({} *self)'.format(func_name, cl.struct_name))
        emitter.emit_line('{')
        for attr, rtype in cl.attributes:
            emitter.emit_line('if (self->{} != {}) {{'.format(attr, rtype.c_undefined_value))
            emitter.emit_dec_ref('self->{}'.format(attr), rtype)
            emitter.emit_line('}')
        emitter.emit_line('Py_TYPE(self)->tp_free((PyObject *)self);')
        emitter.emit_line('}')

    def generate_getseter_declarations(self, cl: ClassIR, emitter: Emitter) -> None:
        for attr, rtype in cl.attributes:
            emitter.emit_line('static PyObject *')
            emitter.emit_line('{}({} *self, void *closure);'.format(getter_name(cl.name, attr),
                                                                cl.struct_name))
            emitter.emit_line('static int')
            emitter.emit_line('{}({} *self, PyObject *value, void *closure);'.format(
                setter_name(cl.name, attr),
                cl.struct_name))

    def generate_getseters_table(self,
                                 cl: ClassIR,
                                 name: str,
                                 emitter: Emitter) -> None:

        emitter.emit_line('static PyGetSetDef {}[] = {{'.format(name))
        for attr, rtype in cl.attributes:
            emitter.emit_line('{{"{}",'.format(attr))
            emitter.emit_line(' (getter){}, (setter){},'.format(getter_name(cl.name, attr),
                                                                setter_name(cl.name, attr)))
            emitter.emit_line(' NULL, NULL},')
        emitter.emit_line('{NULL}  /* Sentinel */')
        emitter.emit_line('};')

    def generate_getseters(self, cl: ClassIR, emitter: Emitter) -> None:
        for attr, rtype in cl.attributes:
            self.generate_getter(cl, attr, rtype, emitter)
            emitter.emit_line('')
            self.generate_setter(cl, attr, rtype, emitter)
            emitter.emit_line('')

    def generate_getter(self,
                        cl: ClassIR,
                        attr: str,
                        rtype: RTType,
                        emitter: Emitter) -> None:
        emitter.emit_line('static PyObject *')
        emitter.emit_line('{}({} *self, void *closure)'.format(getter_name(cl.name, attr),
                                                                            cl.struct_name))
        emitter.emit_line('{')
        emitter.emit_line('if (self->{} == {}) {{'.format(attr, rtype.c_undefined_value))
        emitter.emit_line('PyErr_SetString(PyExc_AttributeError,')
        emitter.emit_line('    "attribute {} of {} undefined");'.format(repr(attr),
                                                                            repr(cl.name)))
        emitter.emit_line('return NULL;')
        emitter.emit_line('}')
        emitter.emit_box('self->{}'.format(attr), 'retval', rtype, 'abort();')
        emitter.emit_line('return retval;')
        emitter.emit_line('}')

    def generate_setter(self,
                        cl: ClassIR,
                        attr: str,
                        rtype: RTType,
                        emitter: Emitter) -> None:
        emitter.emit_line('static int')
        emitter.emit_line('{}({} *self, PyObject *value, void *closure)'.format(
            setter_name(cl.name, attr),
            cl.struct_name))
        emitter.emit_line('{')
        emitter.emit_line('if (self->{} != {}) {{'.format(attr, rtype.c_undefined_value))
        emitter.emit_dec_ref('self->{}'.format(attr), rtype)
        emitter.emit_line('}')
        emitter.emit_line('if (value != NULL) {')
        emitter.emit_unbox_or_cast('value', 'tmp', rtype, 'abort();')
        emitter.emit_line('self->{} = tmp;'.format(attr))
        emitter.emit_line('} else')
        emitter.emit_line('    self->{} = {};'.format(attr, rtype.c_undefined_value))
        emitter.emit_line('return 0;')
        emitter.emit_line('}')


def wrapper_function_header(fn: FuncIR) -> str:
    return 'static PyObject *{prefix}{name}(PyObject *self, PyObject *args, PyObject *kw)'.format(
            prefix=PREFIX,
            name=fn.name)
