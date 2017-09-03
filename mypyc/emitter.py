from typing import List, Dict

from mypyc.common import PREFIX, NATIVE_PREFIX
from mypyc.emitcommon import Emitter, HeaderDeclaration, EmitterContext
from mypyc.emitclass import generate_class
from mypyc.ops import RTType, FuncIR,  c_module_name


class MarkedDeclaration:
    """Add a mark, useful for topological sort."""
    def __init__(self, declaration: HeaderDeclaration, mark: bool) -> None:
        self.declaration = declaration
        self.mark = False


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


def wrapper_function_header(fn: FuncIR) -> str:
    return 'static PyObject *{prefix}{name}(PyObject *self, PyObject *args, PyObject *kw)'.format(
            prefix=PREFIX,
            name=fn.name)
