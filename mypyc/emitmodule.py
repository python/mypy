"""Generate C code for a Python C extension module from Python source code."""

from typing import List

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


class MarkedDeclaration:
    """Add a mark, useful for topological sort."""
    def __init__(self, declaration: HeaderDeclaration, mark: bool) -> None:
        self.declaration = declaration
        self.mark = False


def compile_module_to_c(sources: List[BuildSource], module_name: str, options: Options,
                        alt_lib_path: str) -> str:
    """Compile a Python module to source for a Python C extension module."""
    result = build(sources=sources,
                   options=options,
                   alt_lib_path=alt_lib_path)
    if result.errors:
        raise CompileError(result.errors)

    module = genops.build_ir(result.files[module_name], result.types)
    for fn in module.functions:
        insert_ref_count_opcodes(fn)

    generator = ModuleGenerator(module_name, module)
    return generator.generate_c_module()


def generate_function_declaration(fn: FuncIR, emitter: Emitter) -> None:
    emitter.emit_lines(
        '{};'.format(native_function_header(fn)),
        '{};'.format(wrapper_function_header(fn)))


class ModuleGenerator:
    def __init__(self, module_name: str, module: ModuleIR) -> None:
        self.module_name = module_name
        self.module = module
        self.context = EmitterContext()

    def generate_c_module(self) -> str:
        emitter = Emitter(self.context)

        self.declare_imports(self.module.imports)

        for cl in self.module.classes:
            generate_class(cl, self.module_name, emitter)

        for fn in self.module.functions:
            generate_function_declaration(fn, emitter)

        emitter.emit_line()

        self.generate_module_def(emitter)

        for fn in self.module.functions:
            emitter.emit_line()
            generate_native_function(fn, emitter)
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
        emitter.emit_line('static PyMethodDef module_methods[] = {')
        for fn in self.module.functions:
            emitter.emit_line(
                ('{{"{name}", (PyCFunction){prefix}{name}, METH_VARARGS | METH_KEYWORDS, '
                 'NULL /* docstring */}},').format(
                    name=fn.name,
                    prefix=PREFIX))
        emitter.emit_line('{NULL, NULL, 0, NULL}')
        emitter.emit_line('};')
        emitter.emit_line()

        emitter.emit_lines('static struct PyModuleDef module = {',
                           'PyModuleDef_HEAD_INIT,',
                           '"{}",'.format(self.module_name),
                           'NULL, /* docstring */',
                           '-1,       /* size of per-interpreter state of the module,',
                           '             or -1 if the module keeps state in global variables. */',
                           'module_methods',
                           '};')
        emitter.emit_line()
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
        self.generate_imports_init_section(self.module.imports, emitter)
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
            emitter.emit_line('{} = PyImport_ImportModule("{}");'.format(c_module_name(imp), imp))
            emitter.emit_line('if ({} == NULL)'.format(c_module_name(imp)))
            emitter.emit_line('    return NULL;')
