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
from mypyc.ops import FuncIR, ClassIR, RTType
from mypyc.refcount import insert_ref_count_opcodes


def compile_module_to_c(sources: List[BuildSource], module: str, options: Options,
                        alt_lib_path: str) -> str:
    result = build(sources=sources,
                   options=options,
                   alt_lib_path=alt_lib_path)
    if result.errors:
        raise CompileError(result.errors)

    functions, classes = genops.build_ir(result.files[module], result.types)
    for fn in functions:
        insert_ref_count_opcodes(fn)
    return generate_c_module(module, functions, classes)


def generate_c_module(name: str, fns: List[FuncIR], classes: List[ClassIR]) -> str:
    result = []

    code_generator = CodeGenerator()

    for cl in classes:
        fragments = code_generator.generate_class_declaration(cl, name)
        result.extend(fragments)

    for fn in fns:
        fragments = generate_function_declaration(fn)
        result.extend(fragments)

    result.append('')

    fragments = generate_module_def(name, fns, classes)
    result.extend(fragments)

    for fn in fns:
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


def generate_function_declaration(fn: FuncIR) -> List[str]:
    return [
        '{};'.format(native_function_header(fn)),
        '{};'.format(wrapper_function_header(fn))
    ]


init_func_format = textwrap.dedent("""\
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
        {namespace_setup}
        return m;
    }}
""")


def generate_module_def(module_name: str, fns: List[FuncIR], classes: List[ClassIR]) -> List[str]:
    lines = []
    lines.append('static PyMethodDef module_methods[] = {')
    for fn in fns:
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
    for cl in classes:
        name = cl.name
        type_struct = '{}Type'.format(name)
        init_classes.extend(['{}.tp_new = PyType_GenericNew;'.format(type_struct),
                             '    if (PyType_Ready(&{}) < 0)'.format(type_struct),
                             '        return NULL;'])
        namespace_setup.extend(
            ['Py_INCREF(&{});'.format(type_struct),
             '    PyModule_AddObject(m, "{}", (PyObject *)&{});'.format(name, type_struct)])

    lines.extend(
        init_func_format.format(
            name=module_name,
            init_classes='\n'.join(init_classes),
            namespace_setup='\n'.join(namespace_setup)).splitlines())
    return lines
