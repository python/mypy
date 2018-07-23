"""Code generation for native classes and related wrappers."""

import textwrap

from typing import Optional, List, Tuple

from mypyc.common import PREFIX, NATIVE_PREFIX, REG_PREFIX, DUNDER_PREFIX
from mypyc.emit import Emitter
from mypyc.emitfunc import native_function_header
from mypyc.ops import (
    ClassIR, FuncIR, RType, RTuple, Environment, object_rprimitive, FuncSignature,
    VTableMethod, VTableAttr, VTableEntries
)
from mypyc.sametype import is_same_type
from mypyc.namegen import NameGenerator


def generate_class(cl: ClassIR, module: str, emitter: Emitter) -> None:
    """Generate C code for a class.

    This is the main entry point to the module.
    """
    name = cl.name
    name_prefix = cl.name_prefix(emitter.names)
    fullname = '{}.{}'.format(module, name)

    setup_name = new_name = clear_name = dealloc_name = '0'
    traverse_name = vtable_name = '0'
    if not cl.is_trait:
        setup_name = '{}_setup'.format(name_prefix)
        new_name = '{}_new'.format(name_prefix)
        traverse_name = '{}_traverse'.format(name_prefix)
        clear_name = '{}_clear'.format(name_prefix)
        dealloc_name = '{}_dealloc'.format(name_prefix)
        vtable_name = '{}_vtable'.format(name_prefix)

    getseters_name = '{}_getseters'.format(name_prefix)
    methods_name = '{}_methods'.format(name_prefix)
    base_arg = "&{}".format(
        emitter.type_struct_name(cl.base)) if cl.base and not cl.traits else "0"

    def emit_line() -> None:
        emitter.emit_line()

    emit_line()
    generate_object_struct(cl, emitter)
    emit_line()

    # If there is a __init__ method, generate a function for tp_init and
    # extract the args (which we'll use for the native constructor)
    init_fn = cl.get_method('__init__')
    if init_fn:
        init_name = '{}_init'.format(name_prefix)
        init_args = init_fn.args[1:]
        generate_init_for_class(cl, init_name, init_fn, emitter)
    else:
        init_name = '0'
        init_args = []

    call_fn = cl.get_method('__call__')
    call_name = '{}{}'.format(PREFIX, call_fn.cname(emitter.names)) if call_fn else '0'

    # TODO: Add remaining dunder methods
    index_fn = cl.get_method('__getitem__')
    if index_fn:
        as_mapping_value_name = '{}_as_mapping'.format(name_prefix)
        as_mapping_name = '&{}_as_mapping'.format(name_prefix)
        generate_as_mapping_for_class(index_fn, as_mapping_value_name, emitter)
    else:
        as_mapping_name = '0'

    if not cl.is_trait:
        emitter.emit_line('static PyObject *{}(void);'.format(setup_name))
        # TODO: Use RInstance
        ctor = FuncIR(cl.name, None, module, FuncSignature(init_args, object_rprimitive),
                      [], Environment())
        emitter.emit_line(native_function_header(ctor, emitter) + ';')

        emit_line()
        generate_new_for_class(cl, new_name, vtable_name, setup_name, emitter)
        emit_line()
        generate_traverse_for_class(cl, traverse_name, emitter)
        emit_line()
        generate_clear_for_class(cl, clear_name, emitter)
        emit_line()
        generate_dealloc_for_class(cl, dealloc_name, clear_name, emitter)
        emit_line()
        generate_native_getters_and_setters(cl, emitter)
        vtable_name = generate_vtables(cl, vtable_name, emitter)
        emit_line()
    generate_getseter_declarations(cl, emitter)
    emit_line()
    generate_getseters_table(cl, getseters_name, emitter)
    emit_line()
    generate_methods_table(cl, methods_name, emitter)
    emit_line()

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
            {as_mapping_name},         /* tp_as_mapping */
            0,                         /* tp_hash  */
            {tp_call},                 /* tp_call */
            0,                         /* tp_str */
            0,                         /* tp_getattro */
            0,                         /* tp_setattro */
            0,                         /* tp_as_buffer */
            Py_TPFLAGS_DEFAULT | Py_TPFLAGS_HAVE_GC, /* tp_flags */
            0,                         /* tp_doc */
            (traverseproc){traverse_name}, /* tp_traverse */
            (inquiry){clear_name},     /* tp_clear */
            0,                         /* tp_richcompare */
            0,                         /* tp_weaklistoffset */
            0,                         /* tp_iter */
            0,                         /* tp_iternext */
            {methods_name},            /* tp_methods */
            0,                         /* tp_members */
            {getseters_name},          /* tp_getset */
            {base_arg},                /* tp_base */
            0,                         /* tp_dict */
            0,                         /* tp_descr_get */
            0,                         /* tp_descr_set */
            0,                         /* tp_dictoffset */
            {init_name},               /* tp_init */
            0,                         /* tp_alloc */
            {new_name},                /* tp_new */
        }};\
        """).format(type_struct=emitter.type_struct_name(cl),
                    struct_name=cl.struct_name(emitter.names),
                    fullname=fullname,
                    traverse_name=traverse_name,
                    clear_name=clear_name,
                    dealloc_name=dealloc_name,
                    tp_call=call_name,
                    new_name=new_name,
                    methods_name=methods_name,
                    getseters_name=getseters_name,
                    as_mapping_name=as_mapping_name,
                    init_name=init_name,
                    base_arg=base_arg,
                    ))
    emitter.emit_line()
    if not cl.is_trait:
        generate_setup_for_class(cl, setup_name, vtable_name, emitter)
        emitter.emit_line()
        generate_constructor_for_class(cl, ctor, init_fn, setup_name, vtable_name, emitter)
        emitter.emit_line()
    generate_getseters(cl, emitter)


def getter_name(cl: ClassIR, attribute: str, names: NameGenerator) -> str:
    return names.private_name(cl.module_name, '{}_get{}'.format(cl.name, attribute))


def setter_name(cl: ClassIR, attribute: str, names: NameGenerator) -> str:
    return names.private_name(cl.module_name, '{}_set{}'.format(cl.name, attribute))


def native_getter_name(cl: ClassIR, attribute: str, names: NameGenerator) -> str:
    return names.private_name(cl.module_name, 'native_{}_get{}'.format(cl.name, attribute))


def native_setter_name(cl: ClassIR, attribute: str, names: NameGenerator) -> str:
    return names.private_name(cl.module_name, 'native_{}_set{}'.format(cl.name, attribute))


def generate_object_struct(cl: ClassIR, emitter: Emitter) -> None:
    emitter.emit_lines('typedef struct {',
                       'PyObject_HEAD',
                       'CPyVTableItem *vtable;')
    for base in reversed(cl.base_mro):
        if not base.is_trait:
            for attr, rtype in base.attributes.items():
                emitter.emit_line('{}{};'.format(emitter.ctype_spaced(rtype), attr))
    emitter.emit_line('}} {};'.format(cl.struct_name(emitter.names)))


def generate_native_getters_and_setters(cl: ClassIR,
                                        emitter: Emitter) -> None:
    for attr, rtype in cl.attributes.items():
        # Native getter
        emitter.emit_line('{}{}({} *self)'.format(emitter.ctype_spaced(rtype),
                                                  native_getter_name(cl, attr, emitter.names),
                                                  cl.struct_name(emitter.names)))
        emitter.emit_line('{')
        if rtype.is_refcounted:
            emit_undefined_check(rtype, emitter, attr, '==')
            emitter.emit_lines(
                'PyErr_SetString(PyExc_AttributeError, "attribute {} of {} undefined");'.format(
                    repr(attr), repr(cl.name)),
                '} else {')
            emitter.emit_inc_ref('self->{}'.format(attr), rtype)
            emitter.emit_line('}')
        emitter.emit_line('return self->{};'.format(attr))
        emitter.emit_line('}')
        emitter.emit_line()
        # Native setter
        emitter.emit_line(
            'bool {}({} *self, {}value)'.format(native_setter_name(cl, attr, emitter.names),
                                                cl.struct_name(emitter.names),
                                                emitter.ctype_spaced(rtype)))
        emitter.emit_line('{')
        if rtype.is_refcounted:
            emit_undefined_check(rtype, emitter, attr, '!=')
            emitter.emit_dec_ref('self->{}'.format(attr), rtype)
            emitter.emit_line('}')
        emitter.emit_inc_ref('value'.format(attr), rtype)
        emitter.emit_lines('self->{} = value;'.format(attr),
                           'return 1;',
                           '}')
        emitter.emit_line()


def generate_vtables(base: ClassIR,
                     vtable_name: str,
                     emitter: Emitter) -> str:
    """Emit the vtables for a class.

    This includes both the primary vtable and any trait implementation vtables.

    Returns the expression to use to refer to the vtable, which might be
    different than the name, if there are trait vtables."""

    subtables = []
    for trait, vtable in base.trait_vtables.items():
        name = '{}_{}_trait_vtable'.format(
            base.name_prefix(emitter.names), trait.name_prefix(emitter.names))
        generate_vtable(vtable, name, emitter, [])
        subtables.append((trait, name))

    generate_vtable(base.vtable_entries, vtable_name, emitter, subtables)

    return vtable_name if not subtables else "{} + {}".format(vtable_name, len(subtables) * 2)


def generate_vtable(entries: VTableEntries,
                    vtable_name: str,
                    emitter: Emitter,
                    subtables: List[Tuple[ClassIR, str]]) -> None:
    emitter.emit_line('static CPyVTableItem {}[] = {{'.format(vtable_name))
    if subtables:
        emitter.emit_line('/* Array of trait vtables */')
        for trait, table in subtables:
            emitter.emit_line('(CPyVTableItem)&{}, (CPyVTableItem){},'.format(
                emitter.type_struct_name(trait), table))
        emitter.emit_line('/* Start of real vtable */')

    for entry in entries:
        if isinstance(entry, VTableMethod):
            emitter.emit_line('(CPyVTableItem){}{},'.format(NATIVE_PREFIX,
                                                            entry.method.cname(emitter.names)))
        else:
            cl, attr, is_setter = entry
            namer = native_setter_name if is_setter else native_getter_name
            emitter.emit_line('(CPyVTableItem){},'.format(namer(cl, attr, emitter.names)))
    emitter.emit_line('};')


def generate_setup_for_class(cl: ClassIR,
                             func_name: str,
                             vtable_name: str,
                             emitter: Emitter) -> None:
    """Generate a native function that allocates an instance of a class."""
    emitter.emit_line('static PyObject *')
    emitter.emit_line('{}(void)'.format(func_name))
    emitter.emit_line('{')
    emitter.emit_line('{} *self;'.format(cl.struct_name(emitter.names)))
    emitter.emit_line('self = ({struct} *){type_struct}.tp_alloc(&{type_struct}, 0);'.format(
        struct=cl.struct_name(emitter.names),
        type_struct=emitter.type_struct_name(cl)))
    emitter.emit_line('if (self == NULL)')
    emitter.emit_line('    return NULL;')
    emitter.emit_line('self->vtable = {};'.format(vtable_name))
    for base in reversed(cl.base_mro):
        for attr, rtype in base.attributes.items():
            emitter.emit_line('self->{} = {};'.format(attr, emitter.c_undefined_value(rtype)))
    emitter.emit_line('return (PyObject *)self;')
    emitter.emit_line('}')


def generate_constructor_for_class(cl: ClassIR,
                                   fn: FuncIR,
                                   init_fn: Optional[FuncIR],
                                   setup_name: str,
                                   vtable_name: str,
                                   emitter: Emitter) -> None:
    """Generate a native function that allocates and initializes an instance of a class."""
    emitter.emit_line('{}'.format(native_function_header(fn, emitter)))
    emitter.emit_line('{')
    emitter.emit_line('PyObject *self = {}();'.format(setup_name))
    emitter.emit_line('if (self == NULL)')
    emitter.emit_line('    return NULL;')
    if init_fn is not None:
        args = ', '.join(['self'] + [REG_PREFIX + arg.name for arg in fn.args])
        emitter.emit_line('{}{}({});'.format(NATIVE_PREFIX, init_fn.cname(emitter.names), args))
    emitter.emit_line('return self;')
    emitter.emit_line('}')


def generate_init_for_class(cl: ClassIR,
                            func_name: str,
                            init_fn: FuncIR,
                            emitter: Emitter) -> None:
    """Generate an init function suitable for use as tp_init.

    tp_init needs to be a function that returns an int, and our
    __init__ methods return a PyObject. Translate NULL to -1,
    everything else to 0.
    """
    emitter.emit_line('static int')
    emitter.emit_line(
        '{}(PyObject *self, PyObject *args, PyObject *kwds)'.format(func_name))
    emitter.emit_line('{')
    emitter.emit_line('return {}{}(self, args, kwds) != NULL ? 0 : -1;'.format(
        PREFIX, init_fn.cname(emitter.names)))
    emitter.emit_line('}')


def generate_new_for_class(cl: ClassIR,
                           func_name: str,
                           vtable_name: str,
                           setup_name: str,
                           emitter: Emitter) -> None:
    emitter.emit_line('static PyObject *')
    emitter.emit_line(
        '{}(PyTypeObject *type, PyObject *args, PyObject *kwds)'.format(func_name))
    emitter.emit_line('{')
    # TODO: Check and unbox arguments
    emitter.emit_line('return {}();'.format(setup_name))
    emitter.emit_line('}')


def generate_traverse_for_class(cl: ClassIR,
                                func_name: str,
                                emitter: Emitter) -> None:
    """Emit function that performs cycle GC traversal of an instance."""
    emitter.emit_line('static int')
    emitter.emit_line('{}({} *self, visitproc visit, void *arg)'.format(
        func_name,
        cl.struct_name(emitter.names)))
    emitter.emit_line('{')
    for base in reversed(cl.base_mro):
        for attr, rtype in base.attributes.items():
            emitter.emit_gc_visit('self->{}'.format(attr), rtype)
    emitter.emit_line('return 0;')
    emitter.emit_line('}')


def generate_clear_for_class(cl: ClassIR,
                             func_name: str,
                             emitter: Emitter) -> None:
    emitter.emit_line('static int')
    emitter.emit_line('{}({} *self)'.format(func_name, cl.struct_name(emitter.names)))
    emitter.emit_line('{')
    for base in reversed(cl.base_mro):
        for attr, rtype in base.attributes.items():
            emitter.emit_gc_clear('self->{}'.format(attr), rtype)
    emitter.emit_line('return 0;')
    emitter.emit_line('}')


def generate_dealloc_for_class(cl: ClassIR,
                               dealloc_func_name: str,
                               clear_func_name: str,
                               emitter: Emitter) -> None:
    emitter.emit_line('static void')
    emitter.emit_line('{}({} *self)'.format(dealloc_func_name, cl.struct_name(emitter.names)))
    emitter.emit_line('{')
    emitter.emit_line('PyObject_GC_UnTrack(self);')
    emitter.emit_line('{}(self);'.format(clear_func_name))
    emitter.emit_line('Py_TYPE(self)->tp_free((PyObject *)self);')
    emitter.emit_line('}')


def generate_methods_table(cl: ClassIR,
                           name: str,
                           emitter: Emitter) -> None:
    emitter.emit_line('static PyMethodDef {}[] = {{'.format(name))
    for fn in cl.methods.values():
        emitter.emit_line('{{"{}",'.format(fn.name))
        emitter.emit_line(' (PyCFunction){}{},'.format(PREFIX, fn.cname(emitter.names)))
        emitter.emit_line(' METH_VARARGS | METH_KEYWORDS, NULL},')
    emitter.emit_line('{NULL}  /* Sentinel */')
    emitter.emit_line('};')


def generate_as_mapping_for_class(index_method: FuncIR,
                                  name: str,
                                  emitter: Emitter) -> str:
    emitter.emit_line('static PyMappingMethods {} = {{'.format(name))
    emitter.emit_line('0,        /* mp_length */')
    emitter.emit_line('{}{},     /* mp_subscript */'.format(DUNDER_PREFIX,
                                                            index_method.cname(emitter.names)))
    emitter.emit_line('0,        /* mp_ass_subscript */')
    emitter.emit_line('};')
    return name


def generate_getseter_declarations(cl: ClassIR, emitter: Emitter) -> None:
    if not cl.is_trait:
        for attr in cl.attributes:
            emitter.emit_line('static PyObject *')
            emitter.emit_line('{}({} *self, void *closure);'.format(
                getter_name(cl, attr, emitter.names),
                cl.struct_name(emitter.names)))
            emitter.emit_line('static int')
            emitter.emit_line('{}({} *self, PyObject *value, void *closure);'.format(
                setter_name(cl, attr, emitter.names),
                cl.struct_name(emitter.names)))
    for prop in cl.properties:
        emitter.emit_line('static PyObject *')
        emitter.emit_line('{}({} *self, void *closure);'.format(
            getter_name(cl, prop, emitter.names),
            cl.struct_name(emitter.names)))


def generate_getseters_table(cl: ClassIR,
                             name: str,
                             emitter: Emitter) -> None:
    emitter.emit_line('static PyGetSetDef {}[] = {{'.format(name))
    if not cl.is_trait:
        for attr in cl.attributes:
            emitter.emit_line('{{"{}",'.format(attr))
            emitter.emit_line(' (getter){}, (setter){},'.format(
                getter_name(cl, attr, emitter.names), setter_name(cl, attr, emitter.names)))
            emitter.emit_line(' NULL, NULL},')
    for prop in cl.properties:
        emitter.emit_line('{{"{}",'.format(prop))
        emitter.emit_line(' (getter){},'.format(getter_name(cl, prop, emitter.names)))
        emitter.emit_line('NULL, NULL, NULL},')
    emitter.emit_line('{NULL}  /* Sentinel */')
    emitter.emit_line('};')


def generate_getseters(cl: ClassIR, emitter: Emitter) -> None:
    if not cl.is_trait:
        for i, (attr, rtype) in enumerate(cl.attributes.items()):
            generate_getter(cl, attr, rtype, emitter)
            emitter.emit_line('')
            generate_setter(cl, attr, rtype, emitter)
            if i < len(cl.attributes) - 1:
                emitter.emit_line('')
    for prop, func_ir in cl.properties.items():
        rtype = func_ir.sig.ret_type
        emitter.emit_line('')
        generate_readonly_getter(cl, prop, rtype, func_ir, emitter)


def generate_getter(cl: ClassIR,
                    attr: str,
                    rtype: RType,
                    emitter: Emitter) -> None:
    emitter.emit_line('static PyObject *')
    emitter.emit_line('{}({} *self, void *closure)'.format(getter_name(cl, attr, emitter.names),
                                                           cl.struct_name(emitter.names)))
    emitter.emit_line('{')
    emit_undefined_check(rtype, emitter, attr, '==')
    emitter.emit_line('PyErr_SetString(PyExc_AttributeError,')
    emitter.emit_line('    "attribute {} of {} undefined");'.format(repr(attr),
                                                                    repr(cl.name)))
    emitter.emit_line('return NULL;')
    emitter.emit_line('}')
    emitter.emit_inc_ref('self->{}'.format(attr), rtype)
    emitter.emit_box('self->{}'.format(attr), 'retval', rtype, declare_dest=True)
    emitter.emit_line('return retval;')
    emitter.emit_line('}')


def generate_setter(cl: ClassIR,
                    attr: str,
                    rtype: RType,
                    emitter: Emitter) -> None:
    emitter.emit_line('static int')
    emitter.emit_line('{}({} *self, PyObject *value, void *closure)'.format(
        setter_name(cl, attr, emitter.names),
        cl.struct_name(emitter.names)))
    emitter.emit_line('{')
    if rtype.is_refcounted:
        emit_undefined_check(rtype, emitter, attr, '!=')
        emitter.emit_dec_ref('self->{}'.format(attr), rtype)
        emitter.emit_line('}')
    emitter.emit_line('if (value != NULL) {')
    if rtype.is_unboxed:
        emitter.emit_unbox('value', 'tmp', rtype, custom_failure='return -1;', declare_dest=True)
    elif is_same_type(rtype, object_rprimitive):
        emitter.emit_line('PyObject *tmp = value;')
    else:
        emitter.emit_cast('value', 'tmp', rtype, declare_dest=True)
        emitter.emit_lines('if (!tmp)',
                           '    return -1;')
        emitter.emit_inc_ref('tmp', rtype)
    emitter.emit_line('self->{} = tmp;'.format(attr))
    emitter.emit_line('} else')
    emitter.emit_line('    self->{} = {};'.format(attr, emitter.c_undefined_value(rtype)))
    emitter.emit_line('return 0;')
    emitter.emit_line('}')


def generate_readonly_getter(cl: ClassIR,
                             attr: str,
                             rtype: RType,
                             func_ir: FuncIR,
                             emitter: Emitter) -> None:
    emitter.emit_line('static PyObject *')
    emitter.emit_line('{}({} *self, void *closure)'.format(getter_name(cl, attr, emitter.names),
                                                           cl.struct_name(emitter.names)))
    emitter.emit_line('{')
    if rtype.is_unboxed:
        emitter.emit_line('{}retval = {}{}((PyObject *) self);'.format(
            emitter.ctype_spaced(rtype), NATIVE_PREFIX, func_ir.cname(emitter.names)))
        emitter.emit_box('retval', 'retbox', rtype, declare_dest=True)
        emitter.emit_line('return retbox;')
    else:
        emitter.emit_line('return {}{}((PyObject *) self);'.format(NATIVE_PREFIX,
                                                                   func_ir.cname(emitter.names)))
    emitter.emit_line('}')


def emit_undefined_check(rtype: RType, emitter: Emitter, attr: str, compare: str) ->None:
    if isinstance(rtype, RTuple):
        attr_expr = 'self->{}'.format(attr)
        emitter.emit_line(
            'if ({}) {{'.format(
                emitter.tuple_undefined_check_cond(
                    rtype, attr_expr, emitter.c_undefined_value, compare)))
    else:
        emitter.emit_line(
            'if (self->{} {} {}) {{'.format(attr, compare, emitter.c_undefined_value(rtype)))
