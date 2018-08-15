"""Generate C code for a Python C extension module from Python source code."""

from collections import OrderedDict
from typing import List, Tuple, Dict, Iterable, Set, TypeVar, Optional

from mypy.build import BuildSource, build
from mypy.errors import CompileError
from mypy.options import Options

from mypyc import genops
from mypyc.common import PREFIX, TOP_LEVEL_NAME
from mypyc.emit import EmitterContext, Emitter, HeaderDeclaration
from mypyc.emitfunc import generate_native_function, native_function_header
from mypyc.emitclass import generate_class_type_decl, generate_class
from mypyc.emitwrapper import (
    generate_wrapper_function, wrapper_function_header,
)
from mypyc.ops import FuncIR, ClassIR, ModuleIR, LiteralsMap, format_func
from mypyc.refcount import insert_ref_count_opcodes
from mypyc.exceptions import insert_exception_handling
from mypyc.emit import EmitterContext, Emitter, HeaderDeclaration
from mypyc.namegen import exported_name


class MarkedDeclaration:
    """Add a mark, useful for topological sort."""
    def __init__(self, declaration: HeaderDeclaration, mark: bool) -> None:
        self.declaration = declaration
        self.mark = False


def compile_modules_to_c(sources: List[BuildSource], module_names: List[str], options: Options,
                         use_shared_lib: bool,
                         alt_lib_path: Optional[str] = None,
                         ops: Optional[List[str]] = None) -> str:
    """Compile Python module(s) to C that can be used from Python C extension modules."""
    assert options.strict_optional, 'strict_optional must be turned on'
    result = build(sources=sources,
                   options=options,
                   alt_lib_path=alt_lib_path)
    if result.errors:
        raise CompileError(result.errors)

    # Generate basic IR, with missing exception and refcount handling.
    file_nodes = [result.files[name] for name in module_names]
    literals, modules = genops.build_ir(file_nodes, result.graph, result.types)
    # Insert exception handling.
    for _, module in modules:
        for fn in module.functions:
            insert_exception_handling(fn)
    # Insert refcount handling.
    for _, module in modules:
        for fn in module.functions:
            insert_ref_count_opcodes(fn)
    # Format ops for debugging
    if ops is not None:
        for _, module in modules:
            for fn in module.functions:
                ops.extend(format_func(fn))
                ops.append('')
    # Generate C code.
    source_paths = {module_name: result.files[module_name].path
                    for module_name in module_names}
    generator = ModuleGenerator(literals, modules, source_paths, use_shared_lib)
    return generator.generate_c_for_modules()


def generate_function_declaration(fn: FuncIR, emitter: Emitter) -> None:
    emitter.emit_line('{};'.format(native_function_header(fn.decl, emitter)))
    if fn.name != TOP_LEVEL_NAME:
        emitter.emit_line('{};'.format(wrapper_function_header(fn, emitter.names)))


def encode_as_c_string(s: str) -> Tuple[str, int]:
    """Produce a utf-8 encoded, escaped, quoted C string and its size from a string"""
    # This is a kind of abusive way to do this...
    b = s.encode('utf-8')
    escaped = str(b)[2:-1].replace('"', '\\"')
    return '"{}"'.format(escaped), len(b)


def encode_bytes_as_c_string(b: bytes) -> Tuple[str, int]:
    """Produce a single-escaped, quoted C string and its size from a bytes"""
    # This is a kind of abusive way to do this...
    escaped = str(b)[2:-1].replace('"', '\\"')
    return '"{}"'.format(escaped), len(b)


class ModuleGenerator:
    def __init__(self,
                 literals: LiteralsMap,
                 modules: List[Tuple[str, ModuleIR]],
                 source_paths: Dict[str, str],
                 use_shared_lib: bool) -> None:
        self.literals = literals
        self.modules = modules
        self.source_paths = source_paths
        self.context = EmitterContext([name for name, _ in modules])
        self.names = self.context.names
        self.use_shared_lib = use_shared_lib

    def generate_c_for_modules(self) -> str:
        emitter = Emitter(self.context)

        module_irs = [module_ir for _, module_ir in self.modules]

        for module_name, module in self.modules:
            self.declare_module(module_name, emitter)
            self.declare_internal_globals(module_name, emitter)
            self.declare_imports(module.imports, emitter)

        for identifier in self.literals.values():
            self.declare_static_pyobject(identifier, emitter)

        for module in module_irs:
            for fn in module.functions:
                generate_function_declaration(fn, emitter)

        self.generate_literals(emitter)

        classes = []
        for module_name, module in self.modules:
            classes.extend([(module_name, cl) for cl in module.classes])
        # We must topo sort so that base classes are generated first.
        classes = sort_classes(classes)
        for module_name, cl in classes:
            generate_class_type_decl(cl, emitter)
        for module_name, cl in classes:
            generate_class(cl, module_name, emitter)

        emitter.emit_line()

        # Generate Python extension module definitions and module initialization functions.
        for module_name, module in self.modules:
            self.generate_module_def(emitter, module_name, module)

        for module_name, module in self.modules:
            for fn in module.functions:
                emitter.emit_line()
                generate_native_function(fn, emitter, self.source_paths[module_name], module_name)
                if fn.name != TOP_LEVEL_NAME:
                    emitter.emit_line()
                    generate_wrapper_function(fn, emitter)

        declarations = Emitter(self.context)
        declarations.emit_line('#include <Python.h>')
        declarations.emit_line('#include <CPy.h>')
        declarations.emit_line()

        for declaration in self.toposort_declarations():
            declarations.emit_lines(*declaration.body)

        for static_def in self.context.statics.values():
            declarations.emit_line(static_def)

        return ''.join(declarations.fragments + emitter.fragments)

    def generate_literals(self, emitter: Emitter) -> None:
        emitter.emit_lines(
            'static int CPyLiteralsInit(void)',
            '{',
            'static int is_initialized = 0;',
            'if (is_initialized) return 0;',
            ''
        )

        for (_, literal), identifier in self.literals.items():
            symbol = emitter.static_name(identifier, None)
            if isinstance(literal, int):
                emitter.emit_line(
                    '{} = PyLong_FromString(\"{}\", NULL, 10);'.format(
                        symbol, str(literal))
                )
            elif isinstance(literal, float):
                emitter.emit_line(
                    '{} = PyFloat_FromDouble({});'.format(symbol, str(literal))
                )
            elif isinstance(literal, str):
                emitter.emit_line(
                    '{} = PyUnicode_FromStringAndSize({}, {});'.format(
                        symbol, *encode_as_c_string(literal))
                )
            elif isinstance(literal, bytes):
                emitter.emit_line(
                    '{} = PyBytes_FromStringAndSize({}, {});'.format(
                        symbol, *encode_bytes_as_c_string(literal))
                )
            else:
                assert False, ('Literals must be integers, floating point numbers, or strings,',
                               'but the provided literal is of type {}'.format(type(literal)))
            emitter.emit_lines('if ({} == NULL)'.format(symbol),
                               '    return -1;')


        emitter.emit_lines(
            'is_initialized = 1;',
            'return 0;',
            '}',
        )

    def generate_module_def(self, emitter: Emitter, module_name: str, module: ModuleIR) -> None:
        """Emit the PyModuleDef struct for a module and the module init function."""
        # Emit module methods
        module_prefix = emitter.names.private_name(module_name)
        emitter.emit_line('static PyMethodDef {}module_methods[] = {{'.format(module_prefix))
        for fn in module.functions:
            if fn.class_name is not None or fn.name == TOP_LEVEL_NAME:
                continue
            emitter.emit_line(
                ('{{"{name}", (PyCFunction){prefix}{cname}, METH_VARARGS | METH_KEYWORDS, '
                 'NULL /* docstring */}},').format(
                    name=fn.name,
                    cname=fn.cname(emitter.names),
                    prefix=PREFIX))
        emitter.emit_line('{NULL, NULL, 0, NULL}')
        emitter.emit_line('};')
        emitter.emit_line()

        # Emit module definition struct
        emitter.emit_lines('static struct PyModuleDef {}module = {{'.format(module_prefix),
                           'PyModuleDef_HEAD_INIT,',
                           '"{}",'.format(module_name),
                           'NULL, /* docstring */',
                           '-1,       /* size of per-interpreter state of the module,',
                           '             or -1 if the module keeps state in global variables. */',
                           '{}module_methods'.format(module_prefix),
                           '};')
        emitter.emit_line()
        # Emit module init function. If we are compiling just one module, this
        # will be the C API init function. If we are compiling 2+ modules, we
        # generate a shared library for the modules and shims that call into
        # the shared library, and in this case we use an internal module
        # initialized function that will be called by the shim.
        if not self.use_shared_lib:
            declaration = 'PyMODINIT_FUNC PyInit_{}(void)'.format(module_name)
        else:
            declaration = 'PyObject *CPyInit_{}(void)'.format(exported_name(module_name))
        emitter.emit_lines(declaration,
                           '{')
        module_static = self.module_static_name(module_name, emitter)
        emitter.emit_lines('if ({} != Py_None) {{'.format(module_static),
                           'Py_INCREF({});'.format(module_static),
                           'return {};'.format(module_static),
                           '}')

        emitter.emit_lines('{} = PyModule_Create(&{}module);'.format(module_static, module_prefix),
                           'if ({} == NULL)'.format(module_static),
                           '    return NULL;')
        emitter.emit_line(
            'PyObject *modname = PyObject_GetAttrString((PyObject *){}, "__name__");'.format(
                module_static))

        module_globals = emitter.static_name('globals', module_name)
        emitter.emit_lines('{} = PyModule_GetDict({});'.format(module_globals, module_static),
                           'if ({} == NULL)'.format(module_globals),
                           '    return NULL;')

        # HACK: Manually instantiate generated classes here
        for cl in module.classes:
            if cl.is_generated:
                type_struct = emitter.type_struct_name(cl)
                emitter.emit_lines(
                    '{t} = (PyTypeObject *)CPyType_FromTemplate({t}_template, NULL, modname);'.
                    format(t=type_struct))
                emitter.emit_lines('if (!{})'.format(type_struct),
                                   '    return NULL;')

        emitter.emit_lines('if (CPyLiteralsInit() < 0)',
                           '    return NULL;')

        self.generate_top_level_call(module, emitter)

        emitter.emit_lines('Py_DECREF(modname);')

        emitter.emit_line('return {};'.format(module_static))
        emitter.emit_line('}')

    def generate_top_level_call(self, module: ModuleIR, emitter: Emitter) -> None:
        """Generate call to function representing module top level."""
        # Optimization: we tend to put the top level last, so reverse iterate
        for fn in reversed(module.functions):
            if fn.name == TOP_LEVEL_NAME:
                emitter.emit_lines(
                    'PyObject *result = {}();'.format(emitter.native_function_name(fn.decl)),
                    'if (result == NULL)',
                    '    return NULL;',
                    'Py_DECREF(result);'
                )
                break

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

    def declare_global(self, type_spaced: str, name: str, static: bool=True,
                       initializer: Optional[str] = None) -> None:
        initializer_body = '' if not initializer else ' = {}'.format(initializer)
        static_str = 'static ' if static else ''
        if name not in self.context.declarations:
            self.context.declarations[name] = HeaderDeclaration(
                set(),
                ['{}{}{}{};'.format(static_str, type_spaced, name, initializer_body)],
            )

    def declare_internal_globals(self, module_name: str, emitter: Emitter) -> None:
        static_name = emitter.static_name('globals', module_name)
        self.declare_global('PyObject *', static_name)

    def module_static_name(self, module_name: str, emitter: Emitter) -> str:
        return emitter.static_name('module', module_name)

    def declare_module(self, module_name: str, emitter: Emitter) -> None:
        static_name = self.module_static_name(module_name, emitter)
        self.declare_global('CPyModule *', static_name, initializer='Py_None')

    def declare_imports(self, imps: Iterable[str], emitter: Emitter) -> None:
        for imp in imps:
            self.declare_module(imp, emitter)

    def declare_static_pyobject(self, identifier: str, emitter: Emitter) -> None:
        symbol = emitter.static_name(identifier, None)
        self.declare_global('PyObject *', symbol)


def sort_classes(classes: List[Tuple[str, ClassIR]]) -> List[Tuple[str, ClassIR]]:
    mod_name = {ir: name for name, ir in classes}
    irs = [ir for _, ir in classes]
    deps = OrderedDict()  # type: Dict[ClassIR, Set[ClassIR]]
    for ir in irs:
        if ir not in deps:
            deps[ir] = set()
        if ir.base:
            deps[ir].add(ir.base)
        deps[ir].update(ir.traits)
    sorted_irs = toposort(deps)
    return [(mod_name[ir], ir) for ir in sorted_irs]


T = TypeVar('T')


def toposort(deps: Dict[T, Set[T]]) -> List[T]:
    """Topologically sort a dict from item to dependencies.

    This runs in O(V + E).
    """
    result = []
    visited = set()  # type: Set[T]

    def visit(item: T) -> None:
        if item in visited:
            return

        for child in deps[item]:
            visit(child)

        result.append(item)
        visited.add(item)

    for item in deps:
        visit(item)

    return result
