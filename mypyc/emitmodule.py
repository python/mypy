"""Generate C code for a Python C extension module from Python source code."""

from collections import OrderedDict
from typing import List, Tuple, Dict, Iterable

from mypy.build import BuildSource, build
from mypy.errors import CompileError
from mypy.options import Options

from mypyc import genops
from mypyc.common import PREFIX
from mypyc.emit import EmitterContext, Emitter, HeaderDeclaration
from mypyc.emitfunc import generate_native_function, native_function_header
from mypyc.emitclass import generate_class
from mypyc.emitwrapper import generate_wrapper_function, wrapper_function_header
from mypyc.ops import c_module_name, FuncIR, ClassIR, ModuleIR
from mypyc.refcount import insert_ref_count_opcodes
from mypyc.exceptions import insert_exception_handling


class MarkedDeclaration:
    """Add a mark, useful for topological sort."""
    def __init__(self, declaration: HeaderDeclaration, mark: bool) -> None:
        self.declaration = declaration
        self.mark = False


def compile_module_to_c(sources: List[BuildSource], module_name: str, options: Options,
                        alt_lib_path: str) -> str:
    """Compile a Python module to source for a Python C extension module."""
    assert options.strict_optional, 'strict_optional must be turned on'
    result = build(sources=sources,
                   options=options,
                   alt_lib_path=alt_lib_path)
    if result.errors:
        raise CompileError(result.errors)

    # Generate basic IR, with missing exception and refcount handling.
    module = genops.build_ir(result.files[module_name], result.types)
    # Insert exception handling.
    for fn in module.functions:
        insert_exception_handling(fn)
    # Insert refcount handling.
    for fn in module.functions:
        insert_ref_count_opcodes(fn)
    # Generate C code.
    source_path = result.files[module_name].path
    generator = ModuleGenerator(module_name, module, source_path)
    return generator.generate_c_module()


def generate_function_declaration(fn: FuncIR, emitter: Emitter) -> None:
    emitter.emit_lines(
        '{};'.format(native_function_header(fn)),
        '{};'.format(wrapper_function_header(fn)))


def encode_as_c_string(s: str) -> Tuple[str, int]:
    """Produce a utf-8 encoded, escaped, quoted C string and its size from a string"""
    # This is a kind of abusive way to do this...
    b = s.encode('utf-8')
    escaped = str(b)[2:-1].replace('"', '\\"')
    return '"{}"'.format(escaped), len(b)


class ModuleGenerator:
    def __init__(self, module_name: str, module: ModuleIR, source_path: str) -> None:
        self.module_name = module_name
        self.module = module
        self.source_path = source_path
        self.context = EmitterContext()

    def generate_c_module(self) -> str:
        emitter = Emitter(self.context)

        self.declare_internal_globals()

        self.declare_imports(self.module.imports)

        for symbol in self.module.unicode_literals.values():
            self.declare_static_pyobject(symbol)

        for fn in self.module.functions:
            generate_function_declaration(fn, emitter)

        for cl in self.module.classes:
            generate_class(cl, self.module_name, emitter)


        emitter.emit_line()

        self.generate_module_def(emitter)

        for fn in self.module.functions:
            emitter.emit_line()
            generate_native_function(fn, emitter, self.source_path)
            emitter.emit_line()
            generate_wrapper_function(fn, emitter)

        declarations = Emitter(self.context)
        declarations.emit_line('#include <Python.h>')
        declarations.emit_line('#include <CPy.h>')
        declarations.emit_line()

        for declaration in self.toposort_declarations():
            declarations.emit_lines(*declaration.body)

        return ''.join(declarations.fragments + emitter.fragments)

    def generate_module_def(self, emitter: Emitter) -> None:
        # Emit module methods
        emitter.emit_line('static PyMethodDef module_methods[] = {')
        for fn in self.module.functions:
            emitter.emit_line(
                ('{{"{name}", (PyCFunction){prefix}{name}, METH_VARARGS | METH_KEYWORDS, '
                 'NULL /* docstring */}},').format(
                    name=fn.cname,
                    prefix=PREFIX))
        emitter.emit_line('{NULL, NULL, 0, NULL}')
        emitter.emit_line('};')
        emitter.emit_line()

        # Emit module definition struct
        emitter.emit_lines('static struct PyModuleDef module = {',
                           'PyModuleDef_HEAD_INIT,',
                           '"{}",'.format(self.module_name),
                           'NULL, /* docstring */',
                           '-1,       /* size of per-interpreter state of the module,',
                           '             or -1 if the module keeps state in global variables. */',
                           'module_methods',
                           '};')
        emitter.emit_line()

        # Emit module init function
        emitter.emit_lines('PyMODINIT_FUNC PyInit_{}(void)'.format(self.module_name),
                           '{',
                           'PyObject *m;')
        for cl in self.module.classes:
            type_struct = cl.type_struct
            emitter.emit_lines('if (PyType_Ready(&{}) < 0)'.format(type_struct),
                                '    return NULL;')
        emitter.emit_lines('m = PyModule_Create(&module);',
                           'if (m == NULL)',
                           '    return NULL;')
        emitter.emit_lines('_globals = PyModule_GetDict(m);',
                           'if (_globals == NULL)',
                           '    return NULL;')
        self.generate_imports_init_section(self.module.imports, emitter)

        for unicode_literal, symbol in self.module.unicode_literals.items():
            emitter.emit_lines(
                '{} = PyUnicode_FromStringAndSize({}, {});'.format(
                    symbol, *encode_as_c_string(unicode_literal)),
                'if ({} == NULL)'.format(symbol),
                '    return NULL;',
            )

        for cl in self.module.classes:
            name = cl.name
            type_struct = cl.type_struct
            emitter.emit_lines(
                'Py_INCREF(&{});'.format(type_struct),
                'PyModule_AddObject(m, "{}", (PyObject *)&{});'.format(name, type_struct))
        emitter.emit_line('return m;')
        emitter.emit_line('}')

    def toposort_declarations(self) -> List[HeaderDeclaration]:
        """Topologically sort the declaration dict by dependencies.

        Declarations can require other declarations to come prior in C (such as declaring structs).
        In order to guarantee that the C output will compile the declarations will thus need to
        be properly ordered. This simple DFS guarantees that we have a proper ordering.

        This runs in O(V + E).
        """
        result = []
        marked_declarations = OrderedDict()  # type: Dict[str, MarkedDeclaration]
        for k, v in self.context.declarations.items():
            marked_declarations[k] = MarkedDeclaration(v, False)

        def _toposort_visit(name: str) -> None:
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

    def declare_global(self, type_spaced: str, name: str, static: bool=True) -> None:
        static_str = 'static ' if static else ''
        if name not in self.context.declarations:
            self.context.declarations[name] = HeaderDeclaration(
                set(),
                ['{}{}{};'.format(static_str, type_spaced, name)],
            )

    def declare_internal_globals(self) -> None:
        self.declare_global('PyObject *', '_globals')

    def declare_import(self, imp: str) -> None:
        self.declare_global('CPyModule *', c_module_name(imp))

    def declare_imports(self, imps: Iterable[str]) -> None:
        for imp in imps:
            self.declare_import(imp)

    def declare_static_pyobject(self, symbol: str) -> None:
        self.declare_global('PyObject *', symbol)

    def generate_imports_init_section(self, imps: List[str], emitter: Emitter) -> None:
        for imp in imps:
            emitter.emit_line('{} = PyImport_ImportModule("{}");'.format(c_module_name(imp), imp))
            emitter.emit_line('if ({} == NULL)'.format(c_module_name(imp)))
            emitter.emit_line('    return NULL;')
