"""Generate CPython API wrapper function for a native function."""

from mypyc.common import PREFIX, NATIVE_PREFIX
from mypyc.emit import Emitter
from mypyc.ops import FuncIR, RType, RuntimeArg, is_object_rprimitive
from mypyc.namegen import NameGenerator
from typing import List


def wrapper_function_header(fn: FuncIR, names: NameGenerator) -> str:
    return 'static PyObject *{prefix}{name}(PyObject *self, PyObject *args, PyObject *kw)'.format(
        prefix=PREFIX,
        name=fn.cname(names))


def generate_wrapper_function(fn: FuncIR, emitter: Emitter) -> None:
    """Generates a CPython-compatible wrapper function for a native function.

    In particular, this handles unboxing the arguments, calling the native function, and
    then boxing the return value.
    """
    emitter.emit_line('{} {{'.format(wrapper_function_header(fn, emitter.names)))

    # If fn is a method, then the first argument is a self param
    real_args = list(fn.args)
    if fn.class_name:
        arg = real_args.pop(0)
        emitter.emit_line('PyObject *obj_{} = self;'.format(arg.name))

    optional_args = [arg for arg in fn.args if arg.optional]

    arg_names = ''.join('"{}", '.format(arg.name) for arg in real_args)
    emitter.emit_line('static char *kwlist[] = {{{}0}};'.format(arg_names))
    for arg in real_args:
        emitter.emit_line('PyObject *obj_{}{};'.format(
                          arg.name, ' = NULL' if arg.optional else ''))
    arg_format = '{}{}:f'.format('O' * (len(real_args) - len(optional_args)),
        '|' + 'O' * len(optional_args) if len(optional_args) > 0 else '')
    arg_ptrs = ''.join(', &obj_{}'.format(arg.name) for arg in real_args)
    emitter.emit_lines(
        'if (!PyArg_ParseTupleAndKeywords(args, kw, "{}", kwlist{})) {{'.format(
            arg_format, arg_ptrs),
        'return NULL;',
        '}')
    generate_wrapper_core(fn, emitter, optional_args)
    emitter.emit_line('}')


def dunder_wrapper_header(fn: FuncIR, emitter: Emitter) -> str:
    input_args = ', '.join('PyObject *' for _ in fn.args)
    return 'static PyObject *CPyDunder_{name}({input_args})'.format(
        name=fn.cname(emitter.names),
        input_args=input_args,
    )


def generate_dunder_wrapper(fn: FuncIR, emitter: Emitter) -> None:
    """Generates a wrapper for native __dunder__ methods to be able to fit into the mapping
    protocol slot. This specifically means that the arguments are taken as *PyObjects and returned
    as *PyObjects.
    """
    input_args = ', '.join('PyObject *obj_{}'.format(arg.name) for arg in fn.args)
    emitter.emit_line('static PyObject *CPyDunder_{name}({input_args}) {{'.format(
        name=fn.cname(emitter.names),
        input_args=input_args,
    ))
    generate_wrapper_core(fn, emitter)
    emitter.emit_line('}')


def generate_wrapper_core(fn: FuncIR, emitter: Emitter,
                          optional_args: List[RuntimeArg] = []) -> None:
    """Generates the core part of a wrapper function for a native function.
    This expects each argument as a PyObject * named obj_{arg} as a precondition.
    It converts the PyObject *s to the necessary types, checking and unboxing if necessary,
    makes the call, then boxes the result if necessary and returns it.
    """
    for arg in fn.args:
        generate_arg_check(arg.name, arg.type, emitter, arg in optional_args)
    native_args = ', '.join('arg_{}'.format(arg.name) for arg in fn.args)
    if fn.ret_type.is_unboxed:
        # TODO: The Py_RETURN macros return the correct PyObject * with reference count handling.
        #       Are they relevant?
        emitter.emit_line('{}retval = {}{}({});'.format(emitter.ctype_spaced(fn.ret_type),
                                                        NATIVE_PREFIX,
                                                        fn.cname(emitter.names),
                                                        native_args))
        emitter.emit_error_check('retval', fn.ret_type, 'return NULL;')
        emitter.emit_box('retval', 'retbox', fn.ret_type, declare_dest=True)
        emitter.emit_line('return retbox;')
    else:
        emitter.emit_line('return {}{}({});'.format(NATIVE_PREFIX,
                                                    fn.cname(emitter.names),
                                                    native_args))
        # TODO: Tracebacks?


def generate_arg_check(name: str, typ: RType, emitter: Emitter, optional: bool = False) -> None:
    """Insert a runtime check for argument and unbox if necessary.

    The object is named PyObject *obj_{}. This is expected to generate
    a value of name arg_{} (unboxed if necessary). For each primitive a runtime
    check ensures the correct type.
    """
    if typ.is_unboxed:
        # Borrow when unboxing to avoid reference count manipulation.
        emitter.emit_unbox('obj_{}'.format(name), 'arg_{}'.format(name), typ,
                           'return NULL;', declare_dest=True, borrow=True, optional=optional)
    elif is_object_rprimitive(typ):
        # Trivial, since any object is valid.
        if optional:
            emitter.emit_line('PyObject *arg_{};'.format(name))
            emitter.emit_line('if (obj_{} == NULL) {{'.format(name))
            emitter.emit_line('arg_{} = {};'.format(name, emitter.c_error_value(typ)))
            emitter.emit_lines('} else {', 'arg_{} = obj_{}; '.format(name, name), '}')
        else:
            emitter.emit_line('PyObject *arg_{} = obj_{};'.format(name, name))
    else:
        emitter.emit_cast('obj_{}'.format(name), 'arg_{}'.format(name), typ,
                          declare_dest=True, optional=optional)
        if optional:
            emitter.emit_line('if (obj_{} != NULL && arg_{} == NULL) return NULL;'.format(
                              name, name))
        else:
            emitter.emit_line('if (arg_{} == NULL) return NULL;'.format(name, name))
