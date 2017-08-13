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
)
from mypyc.common import PREFIX
from mypyc.ops import FuncIR, ClassIR, RTType, ModuleIR
from mypyc.refcount import insert_ref_count_opcodes


INIT_FUNC_FORMAT = textwrap.dedent("""\
    static struct PyModuleDef module = {{
        PyModuleDef_HEAD_INIT,
        "{name}",
        NULL, /* docstring */
        -1,       /* size of per-interpreter state of the module,
                     or -1 if the module keeps state in global variables. */
        module_methods
    }};

    PyMODINIT_FUNC PyInit_{name}(void)
    {{
        PyObject *m;
        {init_classes}
        m = PyModule_Create(&module);
        if (m == NULL)
            return NULL;
    {init_modules}
        {namespace_setup}
        return m;
    }}
""")


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
        result = []

        code_generator = CodeGenerator()
        code_generator.declare_imports(self.module.imports)

        for cl in self.module.classes:
            fragments = code_generator.generate_class_declaration(cl, self.module_name)
            result.extend(fragments)

        for fn in self.module.functions:
            fragments = generate_function_declaration(fn)
            result.extend(fragments)

        result.append('')

        fragments = self.generate_module_def()
        result.extend(fragments)

        for fn in self.module.functions:
            result.append('')
            fragments = code_generator.generate_c_for_function(fn)
            result.extend([frag.rstrip() for frag in fragments])
            result.append('')
            fragments = code_generator.generate_wrapper_function(fn)
            result.extend(fragments)

        fresult = []
        fresult.append('#include <Python.h>')
        fresult.append('#include <CPy.h>')
        fresult.append('')

        for declaration in code_generator.toposort_declarations():
            fresult += declaration.body

        fresult += result

        return '\n'.join(fresult)

    def generate_module_def(self) -> List[str]:
        lines = []
        lines.append('static PyMethodDef module_methods[] = {')
        for fn in self.module.functions:
            lines.append(
                ('    {{"{name}", (PyCFunction){prefix}{name}, METH_VARARGS | METH_KEYWORDS, '
                 'NULL /* docstring */}},').format(
                    name=fn.name,
                    prefix=PREFIX))
        lines.append('    {NULL, NULL, 0, NULL}')
        lines.append('};')
        lines.append('')

        init_classes = []
        namespace_setup = []  # type: List[str]
        for cl in self.module.classes:
            name = cl.name
            type_struct = '{}Type'.format(name)
            init_classes.extend(['    if (PyType_Ready(&{}) < 0)'.format(type_struct),
                                 '        return NULL;'])
            namespace_setup.extend(
                ['Py_INCREF(&{});'.format(type_struct),
                 '    PyModule_AddObject(m, "{}", (PyObject *)&{});'.format(name, type_struct)])

        lines.extend(
            INIT_FUNC_FORMAT.format(
                name=self.module_name,
                init_classes='\n'.join(init_classes),
                init_modules='\n'.join(
                    self.code_generator.generate_imports_init_section(self.module.imports)
                ),
                namespace_setup='\n'.join(namespace_setup)).splitlines())
        return lines
