"""Generate CPython API wrapper function for a native function."""

from mypyc.common import PREFIX, NATIVE_PREFIX
from mypyc.emit import Emitter
from mypyc.ops import FuncIR, RType


def wrapper_function_header(fn: FuncIR) -> str:
    return 'static PyObject *{prefix}{name}(PyObject *self, PyObject *args, PyObject *kw)'.format(
            prefix=PREFIX,
            name=fn.cname)


def generate_wrapper_function(fn: FuncIR, emitter: Emitter) -> None:
    """Generates a CPython-compatible wrapper function for a native function.

    In particular, this handles unboxing the arguments, calling the native function, and
    then boxing the return value.
    """
    emitter.emit_line('{} {{'.format(wrapper_function_header(fn)))

    # If fn is a method, then the first argument is a self param
    real_args = fn.args[:]
    if fn.class_name:
        arg = real_args.pop(0)
        emitter.emit_line('PyObject *obj_{} = self;'.format(arg.name))

    arg_names = ''.join('"{}", '.format(arg.name) for arg in real_args)
    emitter.emit_line('static char *kwlist[] = {{{}0}};'.format(arg_names))
    for arg in real_args:
        emitter.emit_line('PyObject *obj_{};'.format(arg.name))
    arg_spec = 'O' * len(real_args)
    arg_ptrs = ''.join(', &obj_{}'.format(arg.name) for arg in real_args)
    emitter.emit_lines(
        'if (!PyArg_ParseTupleAndKeywords(args, kw, "{}:f", kwlist{})) {{'.format(
            arg_spec, arg_ptrs),
        'return NULL;',
        '}')
    for arg in fn.args:
        generate_arg_check(arg.name, arg.type, emitter)
    native_args = ', '.join('arg_{}'.format(arg.name) for arg in fn.args)

    if fn.ret_type.supports_unbox:
        # TODO: The Py_RETURN macros return the correct PyObject * with reference count handling.
        #       Are they relevant?
        ret_type = fn.ret_type
        emitter.emit_line('{}retval = {}{}({});'.format(ret_type.ctype_spaced,
                                                        NATIVE_PREFIX, fn.cname,
                                                        native_args))
        emitter.emit_error_check('retval', ret_type, 'return NULL;')
        emitter.emit_box('retval', 'retbox', ret_type, declare_dest=True)
        emitter.emit_lines('return retbox;')
    else:
        emitter.emit_line('return {}{}({});'.format(NATIVE_PREFIX, fn.cname, native_args))
        # TODO: Tracebacks?
    emitter.emit_line('}')


def generate_arg_check(name: str, typ: RType, emitter: Emitter) -> None:
    """Insert a runtime check for argument and unbox if necessary.

    The object is named PyObject *obj_{}. This is expected to generate
    a value of name arg_{} (unboxed if necessary). For each primitive a runtime
    check ensures the correct type.
    """
    if typ.supports_unbox:
        # Borrow when unboxing to avoid reference count manipulation.
        emitter.emit_unbox('obj_{}'.format(name), 'arg_{}'.format(name), typ,
                           'return NULL;', declare_dest=True, borrow=True)
    else:
        emitter.emit_cast('obj_{}'.format(name), 'arg_{}'.format(name), typ,
                          declare_dest=True)
        emitter.emit_line('if (arg_{} == NULL) return NULL;'.format(name))
