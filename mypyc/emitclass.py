"""Code generation for native classes and related wrappers."""

import textwrap

from mypyc.emit import Emitter
from mypyc.emitfunc import native_function_header
from mypyc.ops import ClassIR, FuncIR, RTType, Environment, type_struct_name


def generate_class(cl: ClassIR, module: str, emitter: Emitter) -> None:
    """Generate C code for a class.

    This is the main entry point to the module.
    """
    name = cl.name
    fullname = '{}.{}'.format(module, name)
    new_name = '{}_new'.format(name)
    dealloc_name = '{}_dealloc'.format(name)
    getseters_name = '{}_getseters'.format(name)
    vtable_name = '{}_vtable'.format(name)

    # Use dummy empty __init__ for now.
    init = FuncIR(cl.name, [], RTType(cl.name), [], Environment())
    emitter.emit_line(native_function_header(init) + ';')
    emitter.emit_line()
    generate_object_struct(cl, emitter)
    emitter.emit_line()
    generate_new_for_class(cl, new_name, vtable_name, emitter)
    emitter.emit_line()
    generate_dealloc_for_class(cl, dealloc_name, emitter)
    emitter.emit_line()
    generate_native_getters_and_setters(cl, emitter)
    generate_vtable(cl, vtable_name, emitter)
    emitter.emit_line()
    generate_getseter_declarations(cl, emitter)
    emitter.emit_line()
    generate_getseters_table(cl, getseters_name, emitter)
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
    generate_constructor_for_class(cl, new_name, vtable_name, emitter)
    emitter.emit_line()
    generate_getseters(cl, emitter)


def getter_name(cl: str, attribute: str) -> str:
    return '{}_get{}'.format(cl, attribute)


def setter_name(cl: str, attribute: str) -> str:
    return '{}_set{}'.format(cl, attribute)


def native_getter_name(cl: str, attribute: str) -> str:
    return 'native_{}_get{}'.format(cl, attribute)


def native_setter_name(cl: str, attribute: str) -> str:
    return 'native_{}_set{}'.format(cl, attribute)


def generate_object_struct(cl: ClassIR, emitter: Emitter) -> None:
    emitter.emit_lines('typedef struct {',
                       'PyObject_HEAD',
                       'CPyVTableItem *vtable;')
    for attr, rtype in cl.attributes:
        emitter.emit_line('{}{};'.format(rtype.ctype_spaced, attr))
    emitter.emit_line('}} {};'.format(cl.struct_name))


def generate_native_getters_and_setters(cl: ClassIR,
                                        emitter: Emitter) -> None:
    for attr, rtype in cl.attributes:
        emitter.emit_line('{}{}({} *self)'.format(rtype.ctype_spaced,
                                               native_getter_name(cl.name, attr),
                                               cl.struct_name))
        emitter.emit_line('{')
        if rtype.is_refcounted:
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
        if rtype.is_refcounted:
            emitter.emit_line('if (self->{} != {}) {{'.format(attr, rtype.c_undefined_value))
            emitter.emit_dec_ref('self->{}'.format(attr), rtype)
            emitter.emit_line('}')
        emitter.emit_inc_ref('value'.format(attr), rtype)
        emitter.emit_line('self->{} = value;'.format(attr))
        emitter.emit_line('}')
        emitter.emit_line()


def generate_vtable(cl: ClassIR,
                    vtable_name: str,
                    emitter: Emitter) -> None:
    emitter.emit_line('static CPyVTableItem {}[] = {{'.format(vtable_name))
    for attr, rtype in cl.attributes:
        emitter.emit_line('(CPyVTableItem){},'.format(native_getter_name(cl.name, attr)))
        emitter.emit_line('(CPyVTableItem){},'.format(native_setter_name(cl.name, attr)))
    emitter.emit_line('};')


def generate_constructor_for_class(cl: ClassIR,
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


def generate_new_for_class(cl: ClassIR,
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


def generate_dealloc_for_class(cl: ClassIR,
                               func_name: str,
                               emitter: Emitter) -> None:
    emitter.emit_line('static void')
    emitter.emit_line('{}({} *self)'.format(func_name, cl.struct_name))
    emitter.emit_line('{')
    for attr, rtype in cl.attributes:
        if rtype.is_refcounted:
            emitter.emit_line('if (self->{} != {}) {{'.format(attr, rtype.c_undefined_value))
            emitter.emit_dec_ref('self->{}'.format(attr), rtype)
            emitter.emit_line('}')
    emitter.emit_line('Py_TYPE(self)->tp_free((PyObject *)self);')
    emitter.emit_line('}')


def generate_getseter_declarations(cl: ClassIR, emitter: Emitter) -> None:
    for attr, rtype in cl.attributes:
        emitter.emit_line('static PyObject *')
        emitter.emit_line('{}({} *self, void *closure);'.format(getter_name(cl.name, attr),
                                                            cl.struct_name))
        emitter.emit_line('static int')
        emitter.emit_line('{}({} *self, PyObject *value, void *closure);'.format(
            setter_name(cl.name, attr),
            cl.struct_name))


def generate_getseters_table(cl: ClassIR,
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


def generate_getseters(cl: ClassIR, emitter: Emitter) -> None:
    for i, (attr, rtype) in enumerate(cl.attributes):
        generate_getter(cl, attr, rtype, emitter)
        emitter.emit_line('')
        generate_setter(cl, attr, rtype, emitter)
        if i < len(cl.attributes) - 1:
            emitter.emit_line('')


def generate_getter(cl: ClassIR,
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


def generate_setter(cl: ClassIR,
                    attr: str,
                    rtype: RTType,
                    emitter: Emitter) -> None:
    emitter.emit_line('static int')
    emitter.emit_line('{}({} *self, PyObject *value, void *closure)'.format(
        setter_name(cl.name, attr),
        cl.struct_name))
    emitter.emit_line('{')
    if rtype.is_refcounted:
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
