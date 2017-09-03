"""Code for creating Python C extension modules from IR (intermediate representation)."""

import textwrap
from typing import List

from mypy.build import BuildSource, build
from mypy.errors import CompileError
from mypy.options import Options

from mypyc import genops
from mypyc.emitter import (
    native_function_header,
    wrapper_function_header,
    CodeGenerator,
    Emitter,
)
from mypyc.common import PREFIX
from mypyc.ops import FuncIR, ClassIR, RTType, ModuleIR
from mypyc.refcount import insert_ref_count_opcodes


def compile_module_to_c(sources: List[BuildSource], module_name: str, options: Options,
                        alt_lib_path: str) -> str:
    result = build(sources=sources,
                   options=options,
                   alt_lib_path=alt_lib_path)
    if result.errors:
        raise CompileError(result.errors)

    module = genops.build_ir(result.files[module_name], result.types)
    for fn in module.functions:
        insert_ref_count_opcodes(fn)

    compiler = ModuleCompiler(module_name, module)
    return compiler.generate_c_module()


def generate_function_declaration(fn: FuncIR) -> List[str]:
    return [
        '{};'.format(native_function_header(fn)),
        '{};'.format(wrapper_function_header(fn))
    ]


class ModuleCompiler:
    def __init__(self, module_name: str, module: ModuleIR) -> None:
        self.module_name = module_name
        self.module = module
        self.code_generator = CodeGenerator()

    def generate_c_module(self) -> str:
        emitter = Emitter()

        code_generator = CodeGenerator()
        code_generator.declare_imports(self.module.imports)

        for cl in self.module.classes:
            fragments = code_generator.generate_class_declaration(cl, self.module_name)
            emitter.emit_lines(*fragments)

        for fn in self.module.functions:
            fragments = generate_function_declaration(fn)
            emitter.emit_lines(*fragments)

        emitter.emit_line()

        self.generate_module_def(emitter)

        for fn in self.module.functions:
            emitter.emit_line()
            code_generator.generate_c_for_function(fn, emitter)
            emitter.emit_line()
            code_generator.generate_wrapper_function(fn, emitter)

        declarations = Emitter()
        declarations.emit_line('#include <Python.h>')
        declarations.emit_line('#include <CPy.h>')
        declarations.emit_line()

        for declaration in code_generator.toposort_declarations():
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
                                '        return NULL;')
        emitter.emit_lines('m = PyModule_Create(&module);',
                           'if (m == NULL)',
                           '    return NULL;')
        self.code_generator.generate_imports_init_section(self.module.imports, emitter)
        for cl in self.module.classes:
            name = cl.name
            type_struct = cl.type_struct
            emitter.emit_lines(
                'Py_INCREF(&{});'.format(type_struct),
                'PyModule_AddObject(m, "{}", (PyObject *)&{});'.format(name, type_struct))
        emitter.emit_line('return m;')
        emitter.emit_line('}')
